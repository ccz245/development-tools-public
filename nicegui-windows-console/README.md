# NiceGUI Windows Console

One window for the day-to-day of development work on a Windows laptop: Claude usage, idle and
power, this machine's load, world clocks with weather, tasks, dictation transcripts,
hotstrings and a launchpad. Built with [NiceGUI](https://nicegui.io); runs as a native window.

## Run it

Needs [uv](https://docs.astral.sh/uv/) and Python 3.11+. Dependencies are declared inside
`console.py`, so there is nothing to install first.

```bash
uv run console.py
```

| Option | Does |
|---|---|
| *(none)* | Native window (pywebview / WebView2) |
| `--browser` | Opens in the default browser instead |
| `--no-show` | Serves only, opens nothing (testing) |
| `--demo` | Generic sample tasks, transcripts and apps: safe to show anywhere |
| `--port N` | Overrides the port (default 9001, from config) |

It listens on `127.0.0.1` only: the page can change power settings and start programs.

## Configure it

`config.example.json` holds the defaults. Put your own values in `config.local.json` next to
it (git-ignored); objects merge, lists replace. The usual overrides:

```json
{
  "owner_name": "Ada",
  "clocks": {"cities": [{"name": "Victoria", "tz": "America/Vancouver", "lat": 48.43, "lon": -123.37}]},
  "transcripts": {"path": "C:/path/to/transcripts", "service_name": "Dictation", "service_match": "dictation_service.py"},
  "apps": [{"name": "Note Taker", "command": ["uv", "run", "notes.py"], "cwd": "C:/Development/notes", "match": "notes.py"}]
}
```

Tasks come from Todoist when the `TODOIST_API_TOKEN` environment variable is set, otherwise
from a local list. Hotstrings and hotkeys live in `hotstrings.json`; the card's **Apply**
button writes the AutoHotkey v2 script from it and (re)starts it.

## The cards

| Card | Shows | Source |
|---|---|---|
| Claude usage | Session (5h) and weekly limits; spend for 7 and 30 days | Claude Code's account endpoint; `~/.claude/projects` logs priced by `pricing.json` |
| Idle and power | Idle time, battery, screen-off and sleep timeouts (editable) | `GetLastInputInfo`, `powercfg` |
| This machine | CPU, memory, GPU, temperatures, top 5 processes | psutil, one process snapshot, a PowerShell sensor probe |
| World clocks | Time, day offset, weather, HH:MM converter | `zoneinfo`, Open-Meteo |
| Tasks | Priority / Today / Upcoming / Projects / Waiting, quick add, drag to reprioritise | Todoist API v1 or a local JSON list |
| Transcripts | Dictation history; click to copy | JSONL written by a dictation service |
| Hotstrings | Prompt and text expansions, hotkeys | `hotstrings.json` |
| Launchpad | Start apps, save and restore window layouts, display and theme | `config.local.json` apps, Win32 window placement |

Cards can be dragged by their handle and hidden; Launchpad brings hidden cards back.

## Structure

```
console.py             Entry point; dependencies declared inline (PEP 723)
config.example.json    Defaults; config.local.json overrides (git-ignored)
pricing.json           Per-model token prices for the spend estimate
hotstrings.json        Prompts, text hotstrings and hotkeys
windows_console/
  app.py               Arguments, NiceGUI start-up
  hub.py               Background collectors shared by every open window
  demo.py              Sample data for --demo
  sources/             One module per data source, no UI
  ui/shell.py          Header and the draggable card grid
  ui/cards/            One module per card
tests/                 uv run --with pytest ... pytest tests (see AGENTS.md)
```
