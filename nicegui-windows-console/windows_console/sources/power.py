"""Idle time, battery, and the screen-off / sleep timeouts of the active power plan."""

from __future__ import annotations

import ctypes
import re
import subprocess
import sys
from dataclasses import dataclass

import psutil

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Minutes offered in the dropdowns; 0 means Never, as in Windows Settings.
TIMEOUT_CHOICES = [0, 1, 2, 3, 5, 10, 15, 20, 25, 30, 45, 60, 120, 180, 240, 300]

# (powercfg subgroup, setting) for `powercfg /q`, and the alias `powercfg /change` takes.
SETTINGS = {
    "screen": ("SUB_VIDEO", "VIDEOIDLE", "monitor-timeout"),
    "sleep": ("SUB_SLEEP", "STANDBYIDLE", "standby-timeout"),
}


def label(minutes: int) -> str:
    if minutes == 0:
        return "Never"
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} hour" + ("s" if hours > 1 else "")
    return f"{minutes} min"


class _LastInputInfo(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def idle_seconds() -> float:
    """Seconds since the last keyboard or mouse input, system-wide."""
    if sys.platform != "win32":
        return 0.0
    info = _LastInputInfo()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    # Both values are 32-bit millisecond tick counts; mask so a wrap after ~49 days stays correct.
    now = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
    return ((now - info.dwTime) & 0xFFFFFFFF) / 1000


@dataclass
class Battery:
    percent: int | None
    plugged: bool  # True on a desktop with no battery


def battery() -> Battery:
    reading = psutil.sensors_battery()
    if reading is None:
        return Battery(None, True)
    return Battery(round(reading.percent), bool(reading.power_plugged))


def _powercfg(*args: str) -> str:
    return subprocess.run(
        ["powercfg", *args], capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW
    ).stdout


def parse_query(output: str) -> tuple[int, int] | None:
    """(AC, DC) seconds from `powercfg /q` output.

    The labels are localised, so this relies on the two current-value lines being the last two
    hex values in the output: AC first, then DC.
    """
    values = re.findall(r":\s*(0x[0-9a-fA-F]+)\s*$", output, flags=re.MULTILINE)
    if len(values) < 2:
        return None
    return int(values[-2], 16), int(values[-1], 16)


def read_timeouts() -> dict[str, dict[str, int]]:
    """{"ac": {"screen": minutes, "sleep": minutes}, "dc": {...}}; missing values are omitted."""
    result: dict[str, dict[str, int]] = {"ac": {}, "dc": {}}
    for kind, (group, setting, _) in SETTINGS.items():
        parsed = parse_query(_powercfg("/q", "SCHEME_CURRENT", group, setting))
        if parsed:
            result["ac"][kind] = parsed[0] // 60
            result["dc"][kind] = parsed[1] // 60
    return result


def set_timeout(kind: str, source: str, minutes: int) -> None:
    """Set a timeout on the active plan, e.g. set_timeout("sleep", "dc", 30)."""
    alias = SETTINGS[kind][2]
    _powercfg("/change", f"{alias}-{source}", str(int(minutes)))
