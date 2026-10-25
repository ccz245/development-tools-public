"""Hotstrings: prompt and text expansions and hotkeys, from hotstrings.json.

Click a prompt or text hotstring to copy its expansion. Apply regenerates the AutoHotkey script
from hotstrings.json, checks it loads, and (re)starts it.
"""

from __future__ import annotations

from nicegui import run, ui

from ...config import APP_DIR, expand
from ...sources import hotstrings


def build(ctx, right) -> None:
    owner = ctx.config.get("owner_name", "")
    ahk = ctx.config["autohotkey"]
    exe, script = expand(ahk["exe"]), expand(ahk["script"])
    spec = hotstrings.load(APP_DIR / "hotstrings.json")

    with right:
        running = ui.label("").classes("wc-tiny")
        ui.button("Apply", icon="sync", on_click=lambda: apply()).props("flat dense size=sm no-caps").classes("wc-btn").tooltip(
            f"Regenerate {script.name} from hotstrings.json and (re)start it"
        )

    def copy(text: str) -> None:
        ui.clipboard.write(text)
        ui.notify("Copied to the clipboard", type="positive", timeout=1200)

    def section(title: str, count: int) -> None:
        with ui.row().classes("items-center gap-2 mt-1"):
            ui.label(title).classes("wc-section")
            ui.label(str(count)).classes("wc-tiny wc-muted")

    def columns(count: int) -> ui.grid:
        """Three columns filled top to bottom, so related triggers read down a column."""
        rows = max(1, -(-count // 3))
        return ui.grid(columns=3).classes("w-full gap-x-4 gap-y-1").style(
            f"grid-auto-flow: column; grid-template-rows: repeat({rows}, auto)"
        )

    prompts = spec.get("prompts", [])
    section("Prompts", len(prompts))
    with columns(len(prompts)):
        for item in prompts:
            text = hotstrings.fill(item["text"], owner)
            with ui.row().classes("items-center no-wrap gap-2 wc-row-hover px-1").on("click", lambda t=text: copy(t)) as row:
                ui.label(item["trigger"]).classes("wc-chip")
                ui.label(item["label"]).classes("wc-small font-medium truncate")
            row.tooltip(text)

    texts = spec.get("text", [])
    section("Text hotstrings", len(texts))
    with columns(len(texts)):
        for item in texts:
            text = hotstrings.fill(item["text"], owner)
            with ui.row().classes("items-center no-wrap gap-2 wc-row-hover px-1").on("click", lambda t=text: copy(t)):
                ui.label(item["trigger"]).classes("wc-chip wc-grey")
                ui.label(hotstrings.text_preview(text)).classes("wc-small truncate")

    keys = spec.get("hotkeys", [])
    section("Hotkeys", len(keys))
    with columns(len(keys)):
        for item in keys:
            with ui.row().classes("items-center no-wrap gap-2 px-1") as row:
                ui.label(hotstrings.key_label(item["keys"])).classes("wc-chip wc-outline")
                ui.label(item["label"]).classes("wc-small truncate")
            row.tooltip(item["label"])

    async def apply() -> None:
        fresh = hotstrings.load(APP_DIR / "hotstrings.json")
        await run.io_bound(hotstrings.write_script, fresh, owner, script)
        if not exe.exists():
            ui.notify(f"Wrote {script.name}; AutoHotkey v2 not found at {exe}", type="warning")
            return
        error = await run.io_bound(hotstrings.validate, exe, script)
        if error:
            ui.notify(f"AutoHotkey rejected the script: {error}", type="negative", multi_line=True)
            return
        await run.io_bound(hotstrings.start, exe, script)
        ui.notify(f"{script.name} applied", type="positive")

    async def refresh() -> None:
        pid = await run.io_bound(hotstrings.running, script)
        running.set_text(f"{script.name} running" if pid else f"{script.name} not running")

    ui.timer(10.0, refresh)
    ui.timer(0.5, refresh, once=True)
