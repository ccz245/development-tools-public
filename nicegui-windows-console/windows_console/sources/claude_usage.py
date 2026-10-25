"""Claude Code spend from the local session logs, and plan limits from the account.

Spend: Claude Code writes one JSONL line per streamed content block under ~/.claude/projects;
assistant lines carry `message.usage`. Several lines share one message, so entries are
de-duplicated on (message id, request id). Cost is an API-equivalent estimate from
pricing.json, never an actual charge.

Limits: the session (5h) and weekly percentages come from the same endpoint Claude Code's
/usage view reads, using the OAuth token Claude Code already stores. The token is read, never
refreshed: refreshing would rotate it underneath Claude Code and sign it out.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

LIMITS_URL = "https://api.anthropic.com/api/oauth/usage"
BLOCK = timedelta(hours=5)


@dataclass(frozen=True)
class Entry:
    ts: datetime  # aware, UTC
    model: str
    cost: float


class Pricing:
    def __init__(self, table: dict[str, Any]):
        self.models: dict[str, dict[str, float]] = table["models"]
        self.default = self.models[table["default"]]
        self.fast_multiplier = float(table.get("fast_multiplier", 1.0))
        # Longest prefix first, so claude-opus-4-8 wins over claude-opus-4.
        self._prefixes = sorted(self.models, key=len, reverse=True)

    @classmethod
    def load(cls, path: Path) -> Pricing:
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def rates(self, model: str) -> dict[str, float]:
        for prefix in self._prefixes:
            if model.startswith(prefix):
                return self.models[prefix]
        return self.default

    def cost(self, model: str, usage: dict[str, Any], speed: str | None = None) -> float:
        rates = self.rates(model)
        cache_split = usage.get("cache_creation") or {}
        write_1h = cache_split.get("ephemeral_1h_input_tokens", 0) or 0
        write_5m = cache_split.get("ephemeral_5m_input_tokens")
        if write_5m is None:  # older logs only carry the total, which was all 5-minute writes
            write_5m = (usage.get("cache_creation_input_tokens", 0) or 0) - write_1h
        dollars = (
            (usage.get("input_tokens", 0) or 0) * rates["input"]
            + (usage.get("output_tokens", 0) or 0) * rates["output"]
            + max(write_5m, 0) * rates["cache_write_5m"]
            + write_1h * rates["cache_write_1h"]
            + (usage.get("cache_read_input_tokens", 0) or 0) * rates["cache_read"]
        ) / 1_000_000
        return dollars * (self.fast_multiplier if speed == "fast" else 1.0)


def parse_line(line: bytes | str, pricing: Pricing) -> tuple[str, Entry] | None:
    """Return (dedupe key, entry) for an assistant line with usage, else None."""
    try:
        record = json.loads(line)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(record, dict) or record.get("type") != "assistant":
        return None
    message = record.get("message") or {}
    usage = message.get("usage")
    model = message.get("model") or ""
    stamp = record.get("timestamp")
    if not usage or not stamp or model.startswith("<"):  # "<synthetic>" lines cost nothing
        return None
    try:
        ts = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    key = f"{message.get('id')}:{record.get('requestId')}"
    return key, Entry(ts.astimezone(timezone.utc), model, pricing.cost(model, usage, usage.get("speed")))


class UsageLog:
    """Reads the logs incrementally: each scan only parses bytes appended since the last one.

    A cold scan of a large log folder takes tens of seconds, so progress (byte offsets, seen
    keys, entries) can be cached to disk; the cache is ignored when pricing.json changes.
    """

    def __init__(self, roots: list[Path], pricing: Pricing, cache: Path | None = None, pricing_key: str = ""):
        self.roots = roots
        self.pricing = pricing
        self._offsets: dict[Path, int] = {}
        self._seen: set[str] = set()
        self.entries: list[Entry] = []
        self._cache = cache
        self._pricing_key = pricing_key
        self._load_cache()

    def _load_cache(self) -> None:
        if not self._cache or not self._cache.exists():
            return
        try:
            data = json.loads(self._cache.read_text(encoding="utf-8"))
            if data.get("pricing") != self._pricing_key:
                return
            self._offsets = {Path(p): o for p, o in data["offsets"].items()}
            self._seen = set(data["seen"])
            self.entries = [Entry(datetime.fromisoformat(ts), model, cost) for ts, model, cost in data["entries"]]
        except (OSError, ValueError, KeyError, TypeError):
            self._offsets, self._seen, self.entries = {}, set(), []

    def save_cache(self) -> None:
        if not self._cache:
            return
        self._cache.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._cache.with_suffix(".tmp")
        tmp.write_text(json.dumps({
            "pricing": self._pricing_key,
            "offsets": {str(p): o for p, o in self._offsets.items()},
            "seen": sorted(self._seen),
            "entries": [[e.ts.isoformat(), e.model, e.cost] for e in self.entries],
        }), encoding="utf-8")
        tmp.replace(self._cache)

    def scan(self) -> list[Entry]:
        added = False
        for root in self.roots:
            if not root.is_dir():
                continue
            for path in root.rglob("*.jsonl"):
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                offset = self._offsets.get(path, 0)
                if size < offset:  # file was rewritten; re-read it, the dedupe set prevents doubles
                    offset = 0
                if size == offset:
                    continue
                with path.open("rb") as handle:
                    handle.seek(offset)
                    chunk = handle.read(size - offset)
                complete = chunk.rfind(b"\n") + 1  # leave a half-written last line for next time
                self._offsets[path] = offset + complete
                for line in chunk[:complete].splitlines():
                    # Cheap byte test first: most lines are user turns and tool results.
                    if b'"assistant"' not in line[:1000] or b'"usage"' not in line:
                        continue
                    parsed = parse_line(line, self.pricing)
                    if parsed and parsed[0] not in self._seen:
                        self._seen.add(parsed[0])
                        self.entries.append(parsed[1])
                        added = True
        if added:
            self.entries.sort(key=lambda e: e.ts)
            self.save_cache()
        return self.entries


def daily_costs(entries: list[Entry], days: int, today: date | None = None) -> list[tuple[date, float]]:
    """Cost per local calendar day for the last `days` days, oldest first, today included."""
    today = today or datetime.now().date()
    totals: dict[date, float] = defaultdict(float)
    for entry in entries:
        totals[entry.ts.astimezone().date()] += entry.cost
    return [(day, totals.get(day, 0.0)) for day in (today - timedelta(days=n) for n in range(days - 1, -1, -1))]


def cumulative(daily: list[tuple[date, float]]) -> list[tuple[date, float]]:
    running, out = 0.0, []
    for day, cost in daily:
        running += cost
        out.append((day, running))
    return out


def current_block(entries: list[Entry], now: datetime | None = None) -> tuple[datetime, datetime] | None:
    """The 5-hour usage window containing `now`, estimated from the logs.

    Windows start on the hour of the first message after the previous window closed, which is
    how Claude Code's own session limit behaves. Used only when the limits endpoint is unavailable.
    """
    now = now or datetime.now(timezone.utc)
    start: datetime | None = None
    for entry in entries:
        if start is None or entry.ts >= start + BLOCK:
            start = entry.ts.replace(minute=0, second=0, microsecond=0)
    if start is None or now >= start + BLOCK:
        return None
    return start, start + BLOCK


@dataclass
class Limit:
    percent: float | None
    resets_at: datetime | None


@dataclass
class Limits:
    session: Limit
    weekly: Limit
    error: str | None = None


def _limit(raw: dict[str, Any] | None) -> Limit:
    if not raw:
        return Limit(None, None)
    resets = raw.get("resets_at")
    utilization = raw.get("utilization")
    return Limit(
        float(utilization) if utilization is not None else None,
        datetime.fromisoformat(resets.replace("Z", "+00:00")) if resets else None,
    )


def fetch_limits(credentials: Path, timeout: float = 10.0) -> Limits:
    empty = Limit(None, None)
    try:
        oauth = json.loads(credentials.read_text(encoding="utf-8"))["claudeAiOauth"]
    except (OSError, KeyError, json.JSONDecodeError):
        return Limits(empty, empty, "Not signed in to Claude Code")
    if oauth.get("expiresAt", 0) / 1000 < time.time():
        return Limits(empty, empty, "Claude Code token expired; open Claude Code to refresh it")
    try:
        response = httpx.get(
            LIMITS_URL,
            headers={"Authorization": f"Bearer {oauth['accessToken']}", "anthropic-beta": "oauth-2025-04-20"},
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as error:
        return Limits(empty, empty, f"Limits unavailable ({type(error).__name__})")
    return Limits(_limit(data.get("five_hour")), _limit(data.get("seven_day")))
