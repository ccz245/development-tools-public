"""Background collection. Every source is polled once here, on app-wide timers, whatever the
number of open windows; cards only read the latest values and their timestamps."""

from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from nicegui import app, run

from . import demo
from .config import APP_DIR, STATE_DIR, JsonState, expand
from .sources import claude_usage, machine, power, procs, transcripts, weather
from .sources.tasks import LocalProvider, Provider, Task, TodoistProvider

log = logging.getLogger("windows_console")


@dataclass
class UsageSummary:
    last7: list[tuple[date, float]]
    last30: list[tuple[date, float]]  # cumulative
    block: tuple[datetime, datetime] | None
    entries: int


@dataclass
class AppStatus:
    name: str
    command: list[str]
    state: procs.Match | None


@dataclass
class Hub:
    config: dict[str, Any]
    demo: bool
    state: JsonState
    loaded: datetime = field(default_factory=datetime.now)
    stamps: dict[str, datetime] = field(default_factory=dict)
    usage: UsageSummary | None = None
    limits: claude_usage.Limits | None = None
    snapshot: machine.Snapshot | None = None
    sensors: machine.Sensors = field(default_factory=machine.Sensors)
    idle: float = 0.0
    battery: power.Battery | None = None
    timeouts: dict[str, dict[str, int]] = field(default_factory=lambda: {"ac": {}, "dc": {}})
    weather: dict[str, weather.Weather | None] = field(default_factory=dict)
    tasks: list[Task] = field(default_factory=list)
    tasks_error: str | None = None
    tasks_version: int = 0
    transcripts: list[transcripts.Transcript] = field(default_factory=list)
    service: procs.Match | None = None
    apps: list[AppStatus] = field(default_factory=list)

    def __post_init__(self) -> None:
        claude = self.config["claude"]
        pricing_file = APP_DIR / "pricing.json"
        self._usage_log = claude_usage.UsageLog(
            [expand(r) for r in claude["log_roots"]],
            claude_usage.Pricing.load(pricing_file),
            cache=STATE_DIR / "usage-cache.json",
            pricing_key=hashlib.sha256(pricing_file.read_bytes()).hexdigest()[:16],
        )
        self._sampler = machine.Sampler()
        self.provider: Provider = self._make_provider()
        path = self.config["transcripts"].get("path")
        self._transcripts = transcripts.TranscriptStore(expand(path) if path else None)

    def _make_provider(self) -> Provider:
        if self.demo:
            demo_file = STATE_DIR / "demo-tasks.json"
            demo.write_tasks(demo_file)
            return LocalProvider(demo_file)
        settings = self.config["tasks"]
        token = os.environ.get(settings.get("todoist_token_env", "TODOIST_API_TOKEN"), "")
        if settings.get("provider") in ("auto", "todoist") and token:
            return TodoistProvider(token)
        return LocalProvider(STATE_DIR / "tasks.json")

    # --- collectors -------------------------------------------------------------------------

    def _stamp(self, name: str) -> None:
        self.stamps[name] = datetime.now()

    async def collect_fast(self) -> None:
        self.idle = power.idle_seconds()

    async def collect_machine(self) -> None:
        self.snapshot = await run.io_bound(self._sampler.sample)
        self._stamp("Processes")

    def _processes(self) -> list[procs.ProcInfo] | None:
        return self.snapshot.all if self.snapshot else None

    async def collect_sensors(self) -> None:
        self.sensors = await run.io_bound(machine.read_sensors)

    async def collect_power(self) -> None:
        self.battery = power.battery()
        self.timeouts = await run.io_bound(power.read_timeouts)

    def _summarise_usage(self) -> UsageSummary:
        started = time.monotonic()
        entries = self._usage_log.scan()
        elapsed = time.monotonic() - started
        if elapsed > 2:
            log.info("usage scan took %.1fs (%d entries)", elapsed, len(entries))
        last30 = claude_usage.daily_costs(entries, 30)
        return UsageSummary(
            claude_usage.daily_costs(entries, 7),
            claude_usage.cumulative(last30),
            claude_usage.current_block(entries),
            len(entries),
        )

    async def collect_usage(self) -> None:
        self.usage = await run.io_bound(self._summarise_usage)
        self._stamp("Usage")

    async def collect_limits(self) -> None:
        claude = self.config["claude"]
        if not claude.get("fetch_limits", True):
            return
        self.limits = await run.io_bound(claude_usage.fetch_limits, expand(claude["credentials"]))
        self._stamp("Limits")

    async def collect_weather(self) -> None:
        for city in self.config["clocks"]["cities"]:
            try:
                self.weather[city["name"]] = await run.io_bound(weather.fetch, city["lat"], city["lon"])
            except Exception as error:  # one city's outage should not blank the others
                log.warning("weather for %s failed: %s", city["name"], error)
                self.weather.setdefault(city["name"], None)

    async def collect_tasks(self) -> None:
        try:
            tasks = await run.io_bound(self.provider.list)
        except Exception as error:
            self.tasks_error = f"{self.provider.name}: {type(error).__name__}"
            log.warning("tasks failed: %s", error)
            return
        self.tasks, self.tasks_error = tasks, None
        self.tasks_version += 1

    async def collect_transcripts(self) -> None:
        if self.demo:
            self.transcripts = demo.transcripts()
            self.service = procs.Match(os.getpid(), self.loaded)
            return
        self.transcripts = await run.io_bound(self._transcripts.load)
        self.service = await run.io_bound(procs.find, self.config["transcripts"].get("service_match", ""), self._processes())

    def app_configs(self) -> list[dict]:
        return demo.APPS if self.demo else self.config.get("apps", [])

    async def collect_apps(self) -> None:
        def scan() -> list[AppStatus]:
            processes = self._processes()
            return [AppStatus(a["name"], a.get("command", []), procs.find(a.get("match", ""), processes)) for a in self.app_configs()]
        self.apps = await run.io_bound(scan)

    def start(self) -> None:
        schedule = [
            (1.0, self.collect_fast),
            (2.0, self.collect_machine),
            (5.0, self.collect_sensors),
            (30.0, self.collect_power),
            (60.0, self.collect_usage),
            (300.0, self.collect_limits),
            (900.0, self.collect_weather),
            (60.0, self.collect_tasks),
            (3.0, self.collect_transcripts),
            (5.0, self.collect_apps),
        ]
        for interval, collector in schedule:
            app.timer(interval, _single_flight(collector))  # fires once immediately, then every interval


def _single_flight(collector):
    """Skip a tick while the previous run is still going (a cold log scan can outlast its
    interval, and two scans over the same reader would race), and log failures."""
    busy = False

    async def tick() -> None:
        nonlocal busy
        if busy:
            return
        busy = True
        try:
            await collector()
        except Exception:
            log.exception("%s failed", collector.__name__)
        finally:
            busy = False

    return tick
