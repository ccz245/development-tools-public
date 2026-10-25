"""World clocks with weather. Typing HH:MM under a city converts every clock to that moment."""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from nicegui import ui

from ...sources import weather
from .. import fmt


def _day_offset(moment: datetime) -> str:
    delta = (moment.date() - datetime.now().astimezone().date()).days
    return "" if delta == 0 else f"{delta:+d} day" + ("s" if abs(delta) > 1 else "")


def build(ctx, right) -> None:
    hub = ctx.hub
    cities = ctx.config["clocks"]["cities"]
    zones = [ZoneInfo(c["tz"]) for c in cities]
    pinned: dict[str, datetime | None] = {"at": None}

    with right:
        local = ui.label("").classes("wc-tiny")
        live = ui.button("Live", icon="restore", on_click=lambda: unpin()).props("flat dense size=sm no-caps").classes("wc-btn")
        live.set_visibility(False)

    times, offsets, inputs, panels = [], [], [], []
    with ui.grid(columns=len(cities)).classes("w-full gap-x-3 gap-y-1"):
        for i, city in enumerate(cities):
            with ui.column().classes("items-center gap-0 min-w-0"):
                ui.label(city["name"]).classes("wc-small wc-muted truncate")
                times.append(ui.label("--:--").classes("wc-huge"))
                offsets.append(ui.label("").classes("wc-tiny wc-muted h-4"))
                inputs.append(
                    ui.input(placeholder="HH:MM").props("dense outlined input-class=text-center").classes("w-full")
                    .on("keydown.enter", lambda _, i=i: pin(i)).on("blur", lambda _, i=i: pin(i))
                )
                panels.append(ui.column().classes("items-center gap-0 w-full mt-2"))

    def unpin() -> None:
        pinned["at"] = None
        for box in inputs:
            box.set_value("")
        live.set_visibility(False)
        tick()

    def pin(index: int) -> None:
        text = (inputs[index].value or "").strip()
        match = re.fullmatch(r"(\d{1,2})[:.]?(\d{2})", text)
        if not match:
            if not text and pinned["at"] is not None and not any((b.value or "").strip() for b in inputs):
                unpin()
            return
        hour, minute = int(match.group(1)), int(match.group(2))
        if hour > 23 or minute > 59:
            ui.notify("Use a 24-hour time such as 09:30", type="warning")
            return
        today_there = datetime.now(zones[index])
        pinned["at"] = today_there.replace(hour=hour, minute=minute, second=0, microsecond=0)
        for j, box in enumerate(inputs):
            if j != index:
                box.set_value("")
        live.set_visibility(True)
        tick()

    def tick() -> None:
        base = pinned["at"]
        local.set_text(f"Local {datetime.now():%H:%M}")
        for i, zone in enumerate(zones):
            moment = base.astimezone(zone) if base else datetime.now(zone)
            times[i].set_text(f"{moment:%H:%M}")
            times[i].classes(add="wc-accent") if base else times[i].classes(remove="wc-accent")
            offsets[i].set_text(_day_offset(moment))

    def draw_weather() -> None:
        for city, panel in zip(cities, panels):
            panel.clear()
            data = hub.weather.get(city["name"])
            with panel:
                if data is None:
                    ui.label("—" if city["name"] in hub.weather else "Loading…").classes("wc-tiny wc-muted")
                    continue
                name, icon = weather.describe(data.code, data.is_day)
                with ui.row().classes("items-center no-wrap gap-1"):
                    ui.icon(icon).classes("text-2xl")
                    ui.label(fmt.temp(data.temp)).classes("wc-big")
                ui.label(name).classes("wc-small")
                ui.label(f"{fmt.temp(data.low)} / {fmt.temp(data.high)}").classes("wc-tiny wc-muted")
                with ui.column().classes("gap-0 mt-1 items-center"):
                    for part, slot in data.parts.items():
                        _, part_icon = weather.describe(slot.code, slot.is_day)
                        with ui.row().classes("items-center no-wrap gap-1 wc-tiny wc-muted"):
                            ui.label(part).classes("w-8 text-right")
                            ui.icon(part_icon).classes("text-sm")
                            ui.label(fmt.temp(slot.temp)).classes("wc-num")
                with ui.row().classes("items-center no-wrap gap-1 mt-1 wc-tiny"):
                    ui.icon("water_drop").classes("text-sm wc-muted")
                    ui.label("—" if data.precip is None else f"{data.precip}%").classes("wc-num")
                with ui.row().classes("items-center no-wrap gap-1 wc-tiny"):
                    ui.icon("wb_twilight").classes("text-sm wc-muted")
                    ui.label(f"{data.sunrise}–{data.sunset}").classes("wc-num")

    drawn = {"key": None}

    def maybe_draw_weather() -> None:
        key = tuple((name, id(w)) for name, w in hub.weather.items())
        if key != drawn["key"]:
            drawn["key"] = key
            draw_weather()

    tick()
    draw_weather()
    ui.timer(1.0, tick)
    ui.timer(5.0, maybe_draw_weather)
