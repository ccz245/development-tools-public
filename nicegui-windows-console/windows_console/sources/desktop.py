"""Window layouts, display mode, and the apps the launchpad starts.

Window layouts: every visible top-level window's placement (including maximised state) is saved
against its executable and title, and restored by matching the same executable, preferring the
same title. Coordinates are physical pixels, so the calls run per-monitor DPI aware.
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

import psutil

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
DPI_PER_MONITOR_V2 = ctypes.c_void_p(-4)


class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.UINT),
        ("flags", wintypes.UINT),
        ("showCmd", wintypes.UINT),
        ("ptMinPosition", wintypes.POINT),
        ("ptMaxPosition", wintypes.POINT),
        ("rcNormalPosition", wintypes.RECT),
    ]


@dataclass
class Window:
    hwnd: int
    exe: str
    title: str


def _user32():
    user32 = ctypes.windll.user32
    user32.SetThreadDpiAwarenessContext(DPI_PER_MONITOR_V2)
    return user32


def list_windows() -> list[Window]:
    """Visible, titled, top-level windows that are not tool windows or cloaked UWP shells."""
    if sys.platform != "win32":
        return []
    user32 = _user32()
    dwmapi = ctypes.windll.dwmapi
    found: list[Window] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.GetWindow(hwnd, 4):  # GW_OWNER: skip owned popups
            return True
        if user32.GetWindowLongW(hwnd, -20) & 0x80:  # GWL_EXSTYLE & WS_EX_TOOLWINDOW
            return True
        cloaked = wintypes.DWORD()
        dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))  # DWMWA_CLOAKED
        if cloaked.value:
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if not length:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        try:
            exe = psutil.Process(pid.value).name()
        except psutil.Error:
            exe = "?"
        found.append(Window(hwnd, exe, buffer.value))
        return True

    user32.EnumWindows(visit, 0)
    return found


def save_layout() -> list[dict]:
    user32 = _user32()
    layout = []
    for window in list_windows():
        placement = WINDOWPLACEMENT()
        placement.length = ctypes.sizeof(placement)
        if not user32.GetWindowPlacement(window.hwnd, ctypes.byref(placement)):
            continue
        rect = placement.rcNormalPosition
        layout.append({
            "exe": window.exe,
            "title": window.title,
            "show": placement.showCmd,
            "rect": [rect.left, rect.top, rect.right, rect.bottom],
        })
    return layout


def restore_layout(layout: list[dict]) -> int:
    """Move matching windows back; returns how many were placed."""
    user32 = _user32()
    remaining = list(layout)
    placed = 0
    for window in list_windows():
        candidates = [s for s in remaining if s["exe"] == window.exe]
        if not candidates:
            continue
        saved = next((s for s in candidates if s["title"] == window.title), candidates[0])
        remaining.remove(saved)
        placement = WINDOWPLACEMENT()
        placement.length = ctypes.sizeof(placement)
        placement.showCmd = saved["show"] or 1  # keeps minimised and maximised windows as they were
        placement.rcNormalPosition = wintypes.RECT(*saved["rect"])
        if user32.SetWindowPlacement(window.hwnd, ctypes.byref(placement)):
            placed += 1
    return placed


def monitor_count() -> int:
    return ctypes.windll.user32.GetSystemMetrics(80) if sys.platform == "win32" else 1  # SM_CMONITORS


def switch_display(mode: str) -> None:
    """mode: "internal" (laptop screen only) or "extend"."""
    subprocess.Popen(["DisplaySwitch.exe", f"/{mode}"], creationflags=NO_WINDOW)


def start_app(command: list[str], cwd: str | None, console: bool) -> int:
    process = subprocess.Popen(
        command,
        cwd=cwd or None,
        creationflags=NEW_CONSOLE if console else NO_WINDOW,
        close_fds=True,
    )
    return process.pid


def stop_app(pid: int) -> None:
    try:
        proc = psutil.Process(pid)
        for child in proc.children(recursive=True):
            child.terminate()
        proc.terminate()
    except psutil.Error:
        pass


def restart_self(argv: list[str], cwd: Path) -> None:
    """Start a fresh copy of this app; it waits for the port to free up before binding."""
    subprocess.Popen([sys.executable, *argv, "--wait-for-port"], cwd=cwd, creationflags=NO_WINDOW, close_fds=True)
