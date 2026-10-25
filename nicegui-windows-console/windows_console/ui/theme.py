"""Colours and shared CSS. Tokens are CSS variables so the light theme is one override block."""

from __future__ import annotations

# ECharts draws on a canvas, so its colours are passed as values rather than CSS variables.
CHART_LINE = "#4fb8cc"
CHART_MUTED = "#8b929c"
CHART_GRID = "rgba(139, 146, 156, 0.18)"

CSS = """
:root {
  --wc-bg: #16181c; --wc-card: #202329; --wc-border: #2d3139; --wc-text: #e6e8eb;
  --wc-muted: #8b929c; --wc-accent: #3fa7bb; --wc-accent-strong: #55c2d4; --wc-chip-text: #ffffff;
  --wc-soft: #2a2e35; --wc-good: #3ecf8e; --wc-warn: #f0a35e; --wc-bad: #ef6b6b; --wc-p2: #f0a35e;
}
body.body--light {
  --wc-bg: #eef1f4; --wc-card: #ffffff; --wc-border: #dadfe6; --wc-text: #1d232b;
  --wc-muted: #5f6873; --wc-accent: #1f8ea3; --wc-accent-strong: #167a8d; --wc-soft: #eef1f4;
}
body { background: var(--wc-bg); color: var(--wc-text); }
.q-header { background: var(--wc-accent) !important; }
.wc-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px;
  grid-auto-flow: row dense; align-items: stretch; width: 100%; }
.wc-card { background: var(--wc-card); border: 1px solid var(--wc-border); border-radius: 10px;
  padding: 12px 14px; min-width: 0; display: flex; flex-direction: column; gap: 10px; }
.wc-card.wc-drop { outline: 2px dashed var(--wc-accent); outline-offset: 2px; }
.wc-span-2 { grid-column: span 2; }
.wc-rows-2 { grid-row: span 2; }
@media (max-width: 1100px) {
  .wc-grid { grid-template-columns: 1fr; }
  .wc-span-2 { grid-column: span 1; }
  .wc-rows-2 { grid-row: span 1; }
}
.wc-title { font-weight: 700; font-size: 15px; }
.wc-muted { color: var(--wc-muted); }
.wc-small { font-size: 12px; }
.wc-tiny { font-size: 11px; }
.wc-mono { font-family: ui-monospace, "Cascadia Mono", Consolas, monospace; }
.wc-big { font-size: 26px; font-weight: 700; line-height: 1.1; font-variant-numeric: tabular-nums; }
.wc-huge { font-size: 30px; font-weight: 700; line-height: 1.05; font-variant-numeric: tabular-nums; }
.wc-num { font-variant-numeric: tabular-nums; }
.wc-accent { color: var(--wc-accent-strong); }
.wc-handle { cursor: grab; color: var(--wc-muted); }
.wc-card-tools { opacity: 0; transition: opacity .15s; }
.wc-card:hover .wc-card-tools { opacity: 1; }
.wc-section { font-size: 11px; font-weight: 700; letter-spacing: .06em; color: var(--wc-muted); text-transform: uppercase; }
.wc-chip { font-family: ui-monospace, "Cascadia Mono", Consolas, monospace; font-size: 12px; padding: 1px 7px;
  border-radius: 4px; background: var(--wc-accent); color: var(--wc-chip-text); white-space: nowrap; }
.wc-chip.wc-grey { background: var(--wc-soft); color: var(--wc-muted); border: 1px solid var(--wc-border); }
.wc-chip.wc-outline { background: transparent; color: var(--wc-muted); border: 1px solid var(--wc-border); }
.wc-row-hover { border-radius: 6px; cursor: pointer; }
.wc-row-hover:hover { background: var(--wc-soft); }
.wc-divider { border-top: 1px solid var(--wc-border); }
.wc-clamp-3 { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.wc-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.wc-btn { text-transform: none !important; font-weight: 600; }
.wc-badge { font-size: 10px; padding: 0 6px; border-radius: 8px; background: var(--wc-good); color: #0d2a1d; font-weight: 700; }
.wc-task { border-radius: 6px; padding: 3px 4px; }
.wc-task:hover { background: var(--wc-soft); }
.wc-task-done { opacity: .35; text-decoration: line-through; }
.wc-drop-zone { border: 1px dashed var(--wc-border); border-radius: 6px; padding: 6px; }
.wc-group-drop { outline: 2px dashed var(--wc-accent); border-radius: 6px; }
"""
