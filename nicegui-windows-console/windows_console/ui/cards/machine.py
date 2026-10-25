"""This machine: CPU, memory, GPU, temperatures, and the busiest processes."""

from __future__ import annotations

from nicegui import ui

from .. import fmt


def build(ctx, right) -> None:
    hub = ctx.hub
    count = ui.label("").classes("wc-tiny")
    count.move(right)

    values: dict[str, ui.label] = {}
    with ui.row().classes("w-full no-wrap justify-between gap-2"):
        for key, caption in (("cpu", "CPU"), ("mem", "Memory"), ("gpu", "GPU"), ("cpu_t", "CPU temp"), ("gpu_t", "GPU temp")):
            with ui.column().classes("gap-0 items-start"):
                ui.label(caption).classes("wc-tiny wc-muted")
                values[key] = ui.label("—").classes("wc-big")

    with ui.expansion("Top 5", icon="list").props("dense").classes("w-full wc-small"):
        mode = ui.toggle({"cpu": "CPU", "mem": "Memory"}, value="cpu").props("dense size=sm")
        rows = ui.column().classes("w-full gap-0")

    def refresh() -> None:
        snap, sensors = hub.snapshot, hub.sensors
        if snap:
            values["cpu"].set_text(fmt.percent(snap.cpu))
            values["mem"].set_text(fmt.percent(snap.memory))
            count.set_text(f"{snap.processes} processes")
        values["gpu"].set_text(fmt.percent(sensors.gpu))
        values["cpu_t"].set_text("—" if sensors.cpu_temp is None else f"{round(sensors.cpu_temp)}°C")
        values["gpu_t"].set_text("—" if sensors.gpu_temp is None else f"{round(sensors.gpu_temp)}°C")

        rows.clear()
        procs = [] if not snap else snap.top if mode.value == "cpu" else snap.top_memory
        with rows:
            for proc in procs:
                with ui.row().classes("w-full no-wrap gap-2 wc-small"):
                    ui.label(proc.name).classes("grow truncate")
                    ui.label(f"{proc.cpu:.1f}%" if mode.value == "cpu" else f"{proc.memory_mb:,.0f} MB").classes("wc-num wc-muted")

    ui.timer(2.0, refresh)
