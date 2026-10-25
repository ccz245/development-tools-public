"""Wire the hub to the page and start NiceGUI."""

from __future__ import annotations

import argparse
import logging
import socket
import time

from nicegui import app, ui

from .config import STATE_DIR, JsonState, load_config
from .hub import Hub
from .ui import shell
from .ui.cards import CARDS


def _wait_for_port(host: str, port: int, seconds: float = 20.0) -> None:
    """After "Refresh app" the old process may hold the port for a moment; wait it out."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind((host, port))
                return
            except OSError:
                time.sleep(0.5)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="NiceGUI Windows Console")
    parser.add_argument("--browser", action="store_true", help="open in the default browser instead of a native window")
    parser.add_argument("--no-show", action="store_true", help="serve only; open nothing (for testing)")
    parser.add_argument("--demo", action="store_true", help="show generic sample tasks, transcripts and apps")
    parser.add_argument("--port", type=int, help="override the port from config")
    parser.add_argument("--wait-for-port", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per poll otherwise
    config = load_config()
    port = args.port or int(config.get("port", 9001))
    host = "127.0.0.1"  # never listen beyond this machine: the page can change power settings and start apps
    if args.wait_for_port:
        _wait_for_port(host, port)

    state = JsonState(STATE_DIR / "state.json", {"dark": True, "order": [], "hidden": []})
    hub = Hub(config, args.demo, state)
    app.on_startup(hub.start)

    @ui.page("/")
    def index() -> None:
        shell.page(hub, CARDS)

    native = not (args.browser or args.no_show)
    ui.run(
        host=host,
        port=port,
        title=config.get("title", "Windows Console"),
        favicon="\U0001f5a5️",
        dark=state.get("dark", True),
        native=native,
        window_size=tuple(config.get("window_size", (1480, 1060))) if native else None,
        show=args.browser,
        reload=False,
        show_welcome_message=False,
    )
