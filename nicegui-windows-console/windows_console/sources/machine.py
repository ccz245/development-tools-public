"""CPU, memory, GPU and temperatures for this machine, plus the busiest processes.

Overall CPU and memory come from psutil; per-process figures from one system snapshot (procs.py).
Windows has no single API for GPU load or temperatures, so one PowerShell probe tries, in order:
nvidia-smi; LibreHardwareMonitor or
OpenHardwareMonitor's WMI namespace when either is running; the GPU-engine performance
counters for load; and the ACPI thermal zone for CPU temperature, which usually needs admin.
Anything none of them answers stays None and shows as a dash.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass, field

import psutil

from . import procs

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

PROBE = r"""
$r = @{ gpu = $null; cpu_temp = $null; gpu_temp = $null }
foreach ($ns in 'root/LibreHardwareMonitor', 'root/OpenHardwareMonitor') {
  try {
    $s = Get-CimInstance -Namespace $ns -ClassName Sensor -ErrorAction Stop
    $c = $s | Where-Object { $_.SensorType -eq 'Temperature' -and $_.Name -match 'CPU Package|Core \(Tctl|CPU Core' } | Select-Object -First 1
    $g = $s | Where-Object { $_.SensorType -eq 'Temperature' -and $_.Name -match 'GPU Core|GPU Hot' } | Select-Object -First 1
    $l = $s | Where-Object { $_.SensorType -eq 'Load' -and $_.Name -eq 'GPU Core' } | Select-Object -First 1
    if ($c) { $r.cpu_temp = [double]$c.Value }
    if ($g) { $r.gpu_temp = [double]$g.Value }
    if ($l) { $r.gpu = [double]$l.Value }
    break
  } catch {}
}
if ($null -eq $r.gpu) {
  try {
    $e = Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine -ErrorAction Stop |
      Where-Object { $_.Name -like '*engtype_3D' }
    $r.gpu = [math]::Min(100, [double](($e | Measure-Object UtilizationPercentage -Sum).Sum))
  } catch {}
}
if ($null -eq $r.cpu_temp) {
  try {
    $z = Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop | Select-Object -First 1
    if ($z) { $r.cpu_temp = [math]::Round($z.CurrentTemperature / 10 - 273.15, 1) }
  } catch {}
}
$r | ConvertTo-Json -Compress
"""


@dataclass
class Proc:
    name: str
    pid: int
    cpu: float  # % of the whole machine
    memory_mb: float


@dataclass
class Snapshot:
    cpu: float
    memory: float
    processes: int
    top: list[Proc] = field(default_factory=list)  # by CPU
    top_memory: list[Proc] = field(default_factory=list)
    all: list[procs.ProcInfo] = field(default_factory=list)  # reused for app and service matching


@dataclass
class Sensors:
    gpu: float | None = None
    cpu_temp: float | None = None
    gpu_temp: float | None = None


class Sampler:
    """Per-process CPU % is the change in CPU time between two snapshots over the wall time."""

    def __init__(self) -> None:
        self._previous: dict[tuple[int, float], int] = {}
        self._previous_at = time.monotonic()
        self._cores = psutil.cpu_count() or 1
        psutil.cpu_percent(None)  # prime: the first call always returns 0

    def sample(self, top: int = 5) -> Snapshot:
        processes = procs.snapshot()
        now = time.monotonic()
        elapsed_ticks = max(now - self._previous_at, 1e-3) * 1e7 * self._cores
        current: dict[tuple[int, float], int] = {}
        loads: list[tuple[float, procs.ProcInfo]] = []
        for proc in processes:
            key = (proc.pid, proc.created)  # pid plus start time, so a reused pid is a new process
            current[key] = proc.cpu_ticks
            before = self._previous.get(key)
            if proc.pid != 0 and before is not None:  # pid 0 is the idle process: its "CPU" is idle time
                loads.append((100 * (proc.cpu_ticks - before) / elapsed_ticks, proc))
        self._previous, self._previous_at = current, now
        loads.sort(key=lambda pair: pair[0], reverse=True)
        by_memory = sorted((p for p in processes if p.pid != 0), key=lambda p: p.working_set, reverse=True)
        return Snapshot(
            cpu=psutil.cpu_percent(None),
            memory=psutil.virtual_memory().percent,
            processes=len(processes),
            top=[Proc(p.name, p.pid, load, p.working_set / 2**20) for load, p in loads[:top]],
            top_memory=[Proc(p.name, p.pid, 0.0, p.working_set / 2**20) for p in by_memory[:top]],
            all=processes,
        )


def _nvidia() -> Sensors | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "--query-gpu=utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, creationflags=NO_WINDOW,
        ).stdout.strip().splitlines()[0]
        load, temp = (float(v) for v in out.split(","))
        return Sensors(gpu=load, gpu_temp=temp)
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


def read_sensors() -> Sensors:
    """Slow (a PowerShell start-up, ~1s): call it every few seconds from a worker thread."""
    sensors = Sensors()
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", PROBE],
            capture_output=True, text=True, timeout=20, creationflags=NO_WINDOW,
        ).stdout
        data = json.loads(out.strip() or "{}")
        sensors = Sensors(data.get("gpu"), data.get("cpu_temp"), data.get("gpu_temp"))
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    nvidia = _nvidia()
    if nvidia:
        sensors.gpu, sensors.gpu_temp = nvidia.gpu, nvidia.gpu_temp
    return sensors
