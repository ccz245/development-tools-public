"""The page: header, and a grid of cards that can be dragged into a new order or hidden."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from nicegui import ui

from ..hub import Hub
from . import theme


@dataclass
class CardDef:
    id: str
    title: str
    icon: str
    build: Callable  # build(ctx, header_right) -> None, called inside the card body
    span: int = 1  # grid columns
    rows: int = 1  # grid rows


class Context:
    """What a card needs: the hub, settings, saved state, and the page's own controls."""

    def __init__(self, hub: Hub, cards: list[CardDef]):
        self.hub = hub
        self.config = hub.config
        self.state = hub.state
        self.cards = {c.id: c for c in cards}
        self.dark = ui.dark_mode(self.state.get("dark", True))
        self.dragging: str | None = None
        self.on_layout_change: list[Callable[[], None]] = []

    # --- layout ---------------------------------------------------------------------------

    def order(self) -> list[str]:
        saved = [i for i in self.state.get("order", []) if i in self.cards]
        return saved + [i for i in self.cards if i not in saved]

    def hidden(self) -> list[str]:
        return [i for i in self.state.get("hidden", []) if i in self.cards]

    def move(self, card_id: str, before: str) -> None:
        if card_id == before:
            return
        order = [i for i in self.order() if i != card_id]
        order.insert(order.index(before), card_id)
        self.state.set("order", order)
        self._changed()

    def hide(self, card_id: str) -> None:
        self.state.set("hidden", sorted(set(self.hidden()) | {card_id}))
        self._changed()

    def show(self, card_id: str) -> None:
        self.state.set("hidden", [i for i in self.hidden() if i != card_id])
        self._changed()

    def toggle_theme(self) -> None:
        self.dark.value = not self.dark.value
        self.state.set("dark", self.dark.value)

    def _changed(self) -> None:
        for callback in self.on_layout_change:
            callback()


def header(ctx: Context) -> None:
    with ui.header().classes("items-center px-4 py-1 gap-2"):
        ui.icon("dashboard_customize").classes("text-xl")
        ui.label(ctx.config.get("title", "Windows Console")).classes("text-lg font-bold")
        stamps = ui.label().classes("ml-auto text-xs opacity-90 wc-num")

    def tick() -> None:
        stamps_by_name = ctx.hub.stamps
        parts = [f"{name} {stamps_by_name[name]:%H:%M:%S}" for name in ("Processes", "Usage", "Limits") if name in stamps_by_name]
        stamps.set_text(" | ".join(parts))

    ui.timer(1.0, tick)


def _card(ctx: Context, card: CardDef) -> None:
    classes = "wc-card" + (" wc-span-2" if card.span == 2 else "") + (" wc-rows-2" if card.rows == 2 else "")
    with ui.element("div").classes(classes) as box:
        with ui.row().classes("items-center w-full no-wrap gap-2"):
            handle = ui.icon("drag_indicator").classes("wc-handle").props("draggable").tooltip("Drag to move this card")
            ui.icon(card.icon).classes("wc-accent text-lg")
            ui.label(card.title).classes("wc-title")
            right = ui.row().classes("ml-auto items-center no-wrap gap-2 wc-small wc-muted")
            ui.button(icon="visibility_off", on_click=lambda: ctx.hide(card.id)).props(
                "flat dense round size=sm"
            ).classes("wc-card-tools").tooltip("Hide card (bring it back from Launchpad)")
        with ui.column().classes("w-full gap-2 grow min-w-0"):
            card.build(ctx, right)

    def start_drag() -> None:
        ctx.dragging = card.id

    def drop() -> None:
        box.classes(remove="wc-drop")
        if ctx.dragging and ctx.dragging != card.id:
            ctx.move(ctx.dragging, card.id)
        ctx.dragging = None

    handle.on("dragstart", start_drag)
    box.on("dragover.prevent", lambda: box.classes(add="wc-drop") if ctx.dragging else None)
    box.on("dragleave", lambda: box.classes(remove="wc-drop"))
    box.on("drop", drop)


def page(hub: Hub, cards: list[CardDef]) -> None:
    ui.add_css(theme.CSS)
    ui.query(".nicegui-content").classes("p-3")
    ctx = Context(hub, cards)
    header(ctx)

    @ui.refreshable
    def grid() -> None:
        with ui.element("div").classes("wc-grid"):
            for card_id in ctx.order():
                if card_id not in ctx.hidden():
                    _card(ctx, ctx.cards[card_id])

    ctx.on_layout_change.append(grid.refresh)
    grid()


def clock(fmt: str = "%H:%M") -> str:
    return datetime.now().strftime(fmt)
