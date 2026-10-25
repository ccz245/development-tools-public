"""Launchpad: start companion apps, save and restore window layouts, display and theme switches."""

from __future__ import annotations

import sys
from datetime import datetime

from nicegui import app, run, ui

from ...config import APP_DIR
from ...sources import desktop


def build(ctx, right) -> None:
    hub = ctx.hub
    state = ctx.state

    with right:
        running_count = ui.label("").classes("wc-tiny")

    def section(title: str) -> None:
        ui.label(title).classes("wc-section mt-1")

    async def launch(config: dict) -> None:
        if not config.get("command"):
            ui.notify(f"No command configured for {config['name']} (apps in config.local.json)", type="warning")
            return
        status = next((a for a in hub.apps if a.name == config["name"]), None)
        if status and status.state:
            ui.notify(f"{config['name']} is already running (PID {status.state.pid})", type="info")
            return
        try:
            pid = await run.io_bound(desktop.start_app, config["command"], config.get("cwd"), config.get("console", False))
        except OSError as error:
            ui.notify(f"Could not start {config['name']}: {error}", type="negative")
            return
        ui.notify(f"Started {config['name']} (PID {pid})", type="positive")
        await hub.collect_apps()

    def restart() -> None:
        argv = [a for a in sys.argv if a != "--wait-for-port"]
        desktop.restart_self(argv, APP_DIR)
        ui.notify("Restarting…")
        app.shutdown()

    section("Apps")
    with ui.row().classes("w-full gap-2"):
        for config in hub.app_configs():
            ui.button(config["name"], icon="play_arrow", on_click=lambda c=config: launch(c)).props("no-caps unelevated").classes("wc-btn")
        ui.button("Refresh app", icon="refresh", on_click=restart).props("no-caps unelevated").classes("wc-btn").tooltip(
            "Restart this console to pick up code and config changes"
        )
    with ui.row().classes("items-center gap-2 wc-tiny"):
        ui.element("span").classes("wc-dot").style("background: var(--wc-good)")
        ui.label(f"Loaded {hub.loaded:%H:%M}")

    section("Screen layout")

    async def save() -> None:
        layout = await run.io_bound(desktop.save_layout)
        state.set("window_layout", {"saved": datetime.now().isoformat(timespec="minutes"), "windows": layout})
        ui.notify(f"Saved the position of {len(layout)} windows", type="positive")
        restore_btn.enable()

    async def restore() -> None:
        saved = state.get("window_layout")
        if not saved:
            ui.notify("No layout saved yet", type="warning")
            return
        placed = await run.io_bound(desktop.restore_layout, saved["windows"])
        ui.notify(f"Restored {placed} of {len(saved['windows'])} windows (saved {saved['saved'].replace('T', ' ')})", type="positive")

    with ui.row().classes("w-full gap-2"):
        ui.button("Save screen layout", icon="save", on_click=save).props("no-caps unelevated").classes("wc-btn")
        restore_btn = ui.button("Restore screen layout", icon="settings_backup_restore", on_click=restore).props("no-caps unelevated").classes("wc-btn")
        if not state.get("window_layout"):
            restore_btn.disable()

    section("Window and display")

    def toggle_display() -> None:
        multi = desktop.monitor_count() > 1
        desktop.switch_display("internal" if multi else "extend")
        ui.notify("Switching to the laptop screen only" if multi else "Extending to all displays")

    with ui.row().classes("w-full gap-2"):
        display_btn = ui.button("", icon="laptop", on_click=toggle_display).props("no-caps unelevated").classes("wc-btn")
        theme_btn = ui.button("", icon="light_mode", on_click=lambda: (ctx.toggle_theme(), label_buttons())).props("no-caps unelevated").classes("wc-btn")
        # Hiding or showing a card rebuilds every card, so this menu is only ever built here.
        hidden = ctx.hidden()
        with ui.button(f"Show hidden cards ({len(hidden)})", icon="visibility").props("no-caps unelevated").classes("wc-btn") as hidden_btn:
            with ui.menu():
                for card_id in hidden:
                    ui.menu_item(ctx.cards[card_id].title, on_click=lambda c=card_id: ctx.show(c))
        hidden_btn.set_enabled(bool(hidden))

    def label_buttons() -> None:
        display_btn.set_text("Switch to Laptop only" if desktop.monitor_count() > 1 else "Extend displays")
        dark = ctx.dark.value
        theme_btn.set_text("Light theme" if dark else "Dark theme")
        theme_btn.props(f"icon={'light_mode' if dark else 'dark_mode'}")

    with ui.grid(columns="1fr auto auto").classes("w-full gap-x-4 gap-y-0 mt-2 wc-small"):
        ui.label("Launcher").classes("wc-tiny wc-muted")
        ui.label("Since").classes("wc-tiny wc-muted text-right")
        ui.label("State").classes("wc-tiny wc-muted text-right")
    table = ui.grid(columns="1fr auto auto").classes("w-full gap-x-4 gap-y-0 wc-small")

    shown = {"key": None}

    def refresh() -> None:
        apps = hub.apps
        running = [a for a in apps if a.state]
        running_count.set_text(f"{len(running)} of {len(apps)} running")
        key = tuple((a.name, a.state.pid if a.state else None) for a in apps)
        if key == shown["key"]:
            return
        shown["key"] = key
        table.clear()
        with table:
            for status in apps:
                ui.label(status.name).classes("truncate")
                ui.label(f"{status.state.started:%H:%M}" if status.state else "–").classes("text-right wc-num")
                ui.label("running" if status.state else "not running").classes("text-right").style(
                    "color: var(--wc-good)" if status.state else "color: var(--wc-muted)"
                )

    label_buttons()
    ui.timer(2.0, refresh)
    ui.timer(5.0, label_buttons)
