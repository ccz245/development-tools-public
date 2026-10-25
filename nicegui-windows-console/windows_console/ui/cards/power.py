"""Idle and power: time since last input, battery, and the plan's screen-off and sleep timeouts."""

from __future__ import annotations

from nicegui import run, ui

from ...sources import power
from .. import fmt

CHOICES = {minutes: power.label(minutes) for minutes in power.TIMEOUT_CHOICES}


def build(ctx, right) -> None:
    hub = ctx.hub
    status = ui.label("").classes("wc-tiny")
    status.move(right)

    with ui.row().classes("items-baseline gap-2"):
        idle = ui.label("—").classes("wc-big")
        ui.label("Idle since last input").classes("wc-small wc-muted")

    selects: dict[tuple[str, str], ui.select] = {}
    badges: dict[str, ui.label] = {}
    syncing = {"on": False}

    def on_change(source: str, kind: str, minutes):
        # Checked here, synchronously: NiceGUI runs an async handler later, after `syncing` is
        # already reset, so a guard inside `change` would let refresh() write values back.
        if syncing["on"] or minutes is None or hub.timeouts.get(source, {}).get(kind) == minutes:
            return None
        return change(source, kind, minutes)

    async def change(source: str, kind: str, minutes: int) -> None:
        hub.timeouts.setdefault(source, {})[kind] = minutes  # first, so refresh() does not flip it back
        await run.io_bound(power.set_timeout, kind, source, minutes)
        where = "plugged in" if source == "ac" else "on battery"
        what = "Screen off" if kind == "screen" else "Sleep"
        ui.notify(f"{what} {where}: {power.label(minutes)}", type="positive")

    for source, title, icon in (("ac", "Plugged in", "power"), ("dc", "On battery", "battery_std")):
        with ui.row().classes("w-full items-center no-wrap gap-2"):
            with ui.row().classes("items-center no-wrap gap-1 w-32"):
                ui.icon(icon).classes("wc-muted")
                ui.label(title).classes("wc-small")
                badges[source] = ui.label("now").classes("wc-badge")
            for kind, caption in (("screen", "Screen off"), ("sleep", "Sleep")):
                selects[(source, kind)] = ui.select(
                    CHOICES,
                    label=caption,
                    on_change=lambda e, s=source, k=kind: on_change(s, k, e.value),
                ).props("dense outlined options-dense").classes("grow min-w-0")

    def refresh() -> None:
        idle.set_text(fmt.idle(hub.idle))
        battery = hub.battery
        if battery:
            plugged = battery.plugged
            status.set_text(("Plugged in" if plugged else "On battery") + (f", battery {battery.percent}%" if battery.percent is not None else ""))
            badges["ac"].set_visibility(plugged)
            badges["dc"].set_visibility(not plugged)
        syncing["on"] = True
        try:
            for (source, kind), select in selects.items():
                value = hub.timeouts.get(source, {}).get(kind)
                if value is not None and value != select.value:
                    if value not in select.options:
                        select.options[value] = power.label(value)  # a value set outside the console
                        select.update()
                    select.set_value(value)
        finally:
            syncing["on"] = False

    ui.timer(1.0, refresh)
