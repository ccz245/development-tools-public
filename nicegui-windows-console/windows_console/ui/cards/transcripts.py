"""Transcripts from the dictation service. Click one to copy it."""

from __future__ import annotations

from nicegui import ui

from .. import fmt

SHOWN = 200


def build(ctx, right) -> None:
    hub = ctx.hub
    settings = ctx.config["transcripts"]
    state = {"query": "", "key": None}

    with right:
        summary = ui.label("").classes("wc-tiny")

    with ui.row().classes("w-full items-center no-wrap gap-2"):
        dot = ui.element("span").classes("wc-dot")
        service = ui.label("").classes("wc-tiny grow truncate")
        ui.input(placeholder="Filter", on_change=lambda e: (state.update(query=(e.value or "").lower()), draw())).props(
            "dense outlined clearable"
        ).classes("w-36")
        ui.button(icon="content_copy", on_click=lambda: copy_all()).props("flat dense round size=sm").tooltip("Copy the transcripts shown")

    def visible():
        query = state["query"]
        items = hub.transcripts
        return [t for t in items if query in t.text.lower()] if query else items

    def copy(text: str) -> None:
        ui.clipboard.write(text)
        ui.notify("Copied to the clipboard", type="positive", timeout=1200)

    def copy_all() -> None:
        items = visible()[:SHOWN]
        copy("\n\n".join(f"[{fmt.stamp(t.ts)}] {t.text}" for t in items))

    with ui.scroll_area().classes("w-full h-[540px]"):
        rows = ui.column().classes("w-full gap-1")
    ui.label("Click a transcript to copy it to the clipboard.").classes("wc-tiny wc-muted")

    def draw() -> None:
        rows.clear()
        items = visible()
        with rows:
            if not items:
                path = settings.get("path")
                hint = "No matches" if state["query"] else (f"No transcripts at {path}" if path else "Set transcripts.path in config.local.json")
                ui.label(hint).classes("wc-small wc-muted")
            for item in items[:SHOWN]:
                with ui.row().classes("w-full no-wrap gap-3 p-1 wc-row-hover wc-divider").on("click", lambda t=item.text: copy(t)):
                    with ui.column().classes("gap-0 w-24 shrink-0"):
                        ui.label(fmt.stamp(item.ts)).classes("wc-small font-bold wc-mono")
                        if item.first is not None or item.second is not None:
                            parts = [f"{v:.1f}" for v in (item.first, item.second) if v is not None]
                            ui.label(" + ".join(parts)).classes("wc-tiny wc-muted wc-mono")
                    ui.label(item.text).classes("wc-small font-medium wc-clamp-3")

    def refresh() -> None:
        running = hub.service
        name = settings.get("service_name", "Service")
        dot.style(f"background: var({'--wc-good' if running else '--wc-muted'})")
        service.set_text(f"{name} running, PID {running.pid} since {running.started:%H:%M}" if running else f"{name} not running")
        summary.set_text(f"{len(hub.transcripts)} transcripts, service {'on' if running else 'off'}")
        key = (len(hub.transcripts), hub.transcripts[0].ts if hub.transcripts else None)
        if key != state["key"]:
            state["key"] = key
            draw()

    ui.timer(2.0, refresh)
    ui.timer(0.3, refresh, once=True)
