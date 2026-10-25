"""One-call process snapshots on Windows.

psutil asks Windows about each process separately, and for protected processes it falls back to
enumerating the whole system each time: about 2.5s per pass over ~400 processes, which starved
every other collector. NtQuerySystemInformation(SystemProcessInformation) returns every
process's name, start time, CPU times and working set in one call, in a few milliseconds.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime

import psutil

STATUS_INFO_LENGTH_MISMATCH = 0xC0000004
SYSTEM_PROCESS_INFORMATION = 5
EPOCH_AS_FILETIME = 116444736000000000  # 1970-01-01 in 100ns ticks since 1601

# Processes whose command line is worth reading when matching by script name.
INTERPRETERS = {"python.exe", "pythonw.exe", "node.exe", "uv.exe", "powershell.exe", "pwsh.exe",
                "cmd.exe", "wscript.exe", "cscript.exe", "java.exe", "javaw.exe", "autohotkey64.exe",
                "autohotkey32.exe", "autohotkey.exe", "autohotkeyux.exe", "electron.exe"}


class _UnicodeString(ctypes.Structure):
    _fields_ = [("Length", wintypes.USHORT), ("MaximumLength", wintypes.USHORT), ("Buffer", ctypes.c_void_p)]


class _ProcessInfo(ctypes.Structure):
    _fields_ = [
        ("NextEntryOffset", wintypes.ULONG),
        ("NumberOfThreads", wintypes.ULONG),
        ("WorkingSetPrivateSize", ctypes.c_longlong),
        ("HardFaultCount", wintypes.ULONG),
        ("NumberOfThreadsHighWatermark", wintypes.ULONG),
        ("CycleTime", ctypes.c_ulonglong),
        ("CreateTime", ctypes.c_longlong),
        ("UserTime", ctypes.c_longlong),
        ("KernelTime", ctypes.c_longlong),
        ("ImageName", _UnicodeString),
        ("BasePriority", wintypes.LONG),
        ("UniqueProcessId", ctypes.c_void_p),
        ("InheritedFromUniqueProcessId", ctypes.c_void_p),
        ("HandleCount", wintypes.ULONG),
        ("SessionId", wintypes.ULONG),
        ("UniqueProcessKey", ctypes.c_void_p),
        ("PeakVirtualSize", ctypes.c_size_t),
        ("VirtualSize", ctypes.c_size_t),
        ("PageFaultCount", wintypes.ULONG),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
    ]


@dataclass(frozen=True)
class ProcInfo:
    pid: int
    name: str
    created: float  # epoch seconds; 0 for the idle and system processes
    cpu_ticks: int  # user + kernel, 100ns units
    working_set: int  # bytes


def _windows_snapshot() -> list[ProcInfo]:
    ntdll = ctypes.windll.ntdll
    size = 1 << 20
    while True:
        buffer = ctypes.create_string_buffer(size)
        needed = wintypes.ULONG()
        status = ntdll.NtQuerySystemInformation(SYSTEM_PROCESS_INFORMATION, buffer, size, ctypes.byref(needed)) & 0xFFFFFFFF
        if status == STATUS_INFO_LENGTH_MISMATCH:
            size = max(size * 2, needed.value + 65536)
            continue
        if status != 0:
            raise OSError(f"NtQuerySystemInformation failed: 0x{status:08X}")
        break
    base = ctypes.addressof(buffer)
    offset, rows = 0, []
    while True:
        info = _ProcessInfo.from_address(base + offset)
        name = ctypes.wstring_at(info.ImageName.Buffer, info.ImageName.Length // 2) if info.ImageName.Buffer else ""
        pid = info.UniqueProcessId or 0
        created = (info.CreateTime - EPOCH_AS_FILETIME) / 1e7 if info.CreateTime else 0.0
        rows.append(ProcInfo(pid, name or ("System Idle Process" if pid == 0 else "System"), created,
                             info.UserTime + info.KernelTime, info.WorkingSetSize))
        if not info.NextEntryOffset:
            return rows
        offset += info.NextEntryOffset


def _portable_snapshot() -> list[ProcInfo]:
    rows = []
    for proc in psutil.process_iter():
        try:
            times = proc.cpu_times()
            rows.append(ProcInfo(proc.pid, proc.name(), proc.create_time(), int((times.user + times.system) * 1e7), proc.memory_info().rss))
        except psutil.Error:
            continue
    return rows


def snapshot() -> list[ProcInfo]:
    return _windows_snapshot() if sys.platform == "win32" else _portable_snapshot()


@dataclass
class Match:
    pid: int
    started: datetime


def find(match: str, processes: list[ProcInfo] | None = None) -> Match | None:
    """The first process whose name, or (for interpreters) command line, contains `match`."""
    if not match:
        return None
    needle = match.lower()
    processes = processes if processes is not None else snapshot()
    for proc in processes:
        if needle in proc.name.lower():
            return Match(proc.pid, datetime.fromtimestamp(proc.created))
    for proc in processes:
        if proc.name.lower() not in INTERPRETERS:
            continue
        try:
            cmdline = " ".join(psutil.Process(proc.pid).cmdline()).lower()
        except psutil.Error:
            continue
        if needle in cmdline:
            return Match(proc.pid, datetime.fromtimestamp(proc.created))
    return None
