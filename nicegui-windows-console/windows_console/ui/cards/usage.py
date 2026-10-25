"""Claude usage: plan limits, and API-equivalent spend from Claude Code's local logs."""

from __future__ import annotations

from datetime import datetime, timezone

from nicegui import ui

from .. import fmt, theme


def _chart(labels: list[str], values: list[float], interval: int) -> dict:
    return {
        "animation": False,
        "grid": {"left": 46, "right": 10, "top": 10, "bottom": 24},
        "tooltip": {"trigger": "axis", ":valueFormatter": "v => '$' + v.toFixed(2)"},
        "xAxis": {
            "type": "category",
            "data": labels,
            "boundaryGap": False,
            "axisLabel": {"color": theme.CHART_MUTED, "fontSize": 10, "interval": interval},
            "axisLine": {"lineStyle": {"color": theme.CHART_GRID}},
            "axisTick": {"show": False},
        },
        "yAxis": {
            "type": "value",
            "splitNumber": 2,
            "axisLabel": {"color": theme.CHART_MUTED, "fontSize": 10, "formatter": "${value}"},
            "splitLine": {"lineStyle": {"color": theme.CHART_GRID}},
        },
        "series": [{
            "type": "line",
            "data": values,
            "symbol": "circle",
            "symbolSize": 6,
            "lineStyle": {"color": theme.CHART_LINE, "width": 2},
            "itemStyle": {"color": theme.CHART_LINE},
        }],
    }


def _limit(title: str):
    """A big percentage beside a small title / time-left / reset-time stack."""
    with ui.row().classes("items-start no-wrap gap-3"):
        pct = ui.label("—").classes("wc-huge")
        with ui.column().classes("gap-0"):
            ui.label(title).classes("wc-tiny wc-muted")
            left = ui.label("—").classes("text-lg font-bold wc-num leading-tight")
            reset = ui.label("").classes("wc-tiny wc-muted")
    return pct, left, reset


def build(ctx, right) -> None:
    hub = ctx.hub
    with ui.row().classes("w-full no-wrap justify-between gap-4"):
        session = _limit("Session (5h)")
        weekly = _limit("Weekly")
    note = ui.label("").classes("wc-tiny wc-muted")

    with ui.row().classes("w-full no-wrap gap-4 grow"):
        with ui.column().classes("w-1/2 gap-0 min-w-0"):
            with ui.row().classes("items-baseline gap-2"):
                week_total = ui.label("—").classes("wc-big")
                ui.label("last 7 days").classes("wc-small wc-muted")
            week_chart = ui.echart(_chart([], [], 0)).classes("w-full h-44")
        with ui.column().classes("w-1/2 gap-0 min-w-0"):
            with ui.row().classes("items-baseline gap-2"):
                month_total = ui.label("—").classes("wc-big")
                ui.label("rolling 30 days").classes("wc-small wc-muted")
            month_chart = ui.echart(_chart([], [], 6)).classes("w-full h-44")
    ui.label("API-equivalent estimate from local Claude Code logs; a subscription is flat-rate.").classes("wc-tiny wc-muted")

    shown = {"entries": -1}

    def set_limit(widgets, percent, resets: datetime | None, reset_fmt: str) -> None:
        pct, left, reset = widgets
        pct.set_text(fmt.percent(percent))
        if resets:
            now = datetime.now(timezone.utc)
            left.set_text(fmt.duration(resets - now))
            reset.set_text(f"until reset at {resets.astimezone():{reset_fmt}}")
        else:
            left.set_text("—")
            reset.set_text("")

    def refresh() -> None:
        limits, usage = hub.limits, hub.usage
        if limits and not limits.error:
            set_limit(session, limits.session.percent, limits.session.resets_at, "%H:%M")
            set_limit(weekly, limits.weekly.percent, limits.weekly.resets_at, "%a %H:%M")
            note.set_text("")
        else:
            # No limits endpoint: the 5-hour window can still be estimated from the logs.
            block = usage.block if usage else None
            set_limit(session, None, block[1] if block else None, "%H:%M")
            set_limit(weekly, None, None, "")
            note.set_text((limits.error if limits else "Reading limits…") + (" · session window estimated from logs" if block else ""))

        if usage and usage.entries != shown["entries"]:
            shown["entries"] = usage.entries
            week_total.set_text(fmt.money(sum(c for _, c in usage.last7)))
            week_chart.options.update(_chart([f"{d:%a}" for d, _ in usage.last7], [round(c, 2) for _, c in usage.last7], 0))
            week_chart.update()
            month_total.set_text(fmt.money(usage.last30[-1][1] if usage.last30 else 0))
            month_chart.options.update(_chart([f"{d:%b} {d.day:02d}" for d, _ in usage.last30], [round(c, 2) for _, c in usage.last30], 6))
            month_chart.update()

    ui.timer(5.0, refresh)
    ui.timer(0.5, refresh, once=True)
