# AGENTS.md: nicegui-windows-console

Topic-specific notes; the repo's own rules in `../AGENTS.md` apply first, above all: this repo
is public, so no client names, client data or personal details in code, config, tests or
commit messages. Personal values go in `config.local.json`, which is git-ignored.

## Structure

```
console.py             Entry point (PEP 723 inline dependencies)
config.example.json    Defaults; config.local.json overrides, git-ignored
pricing.json           Token prices for the Claude spend estimate
hotstrings.json        Source for the Hotstrings card and the generated AutoHotkey script
windows_console/       app.py, hub.py, demo.py, config.py, sources/, ui/
tests/                 Source-level tests: parsing and arithmetic, no network
```

## Running and testing

```bash
uv run console.py --no-show --demo        # server only on 127.0.0.1:9001, sample data
uv run --no-project --with pytest --with "nicegui>=3.18,<4" --with psutil --with tzdata pytest -q tests
```

Port 9001 is registered in `shared-utilities/app-hosting/ports.toml`; change it there too.

## Rules that bite

- **Never poll per process through psutil on Windows.** One pass over ~400 processes takes
  ~2.5s and starves every other collector through the GIL. Use `sources/procs.py`, a single
  `NtQuerySystemInformation` call, and read a command line only for interpreter processes.
- **Every collector runs single-flight** (`hub._single_flight`). A cold scan of the Claude
  logs (1.6 GB here) can outlast its interval; overlapping scans over one reader race.
- **Programmatic `select.set_value` fires `on_change`, and an async handler runs later.** Guard
  side effects synchronously and compare against the known value, or a refresh writes the
  current settings back to the system (`ui/cards/power.py`).
- **The Claude OAuth token is read, never refreshed.** Refreshing rotates it under Claude Code.
- **Todoist priorities are inverted at the API edge** (API 4 = P1). Inside the app, 1 is urgent.
- **The generated AutoHotkey script is not in the repo.** It contains `owner_name`; it is written
  to `%LOCALAPPDATA%` on Apply. Check it with `AutoHotkey64.exe /ErrorStdOut /Validate <file>`.
- **Test interactive features in `--demo`.** Real mode writes to Todoist, power settings,
  window positions and displays.
