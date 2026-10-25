# Design

Rebuilt on 2026-10-24 from a screenshot of an earlier NiceGUI app; the original source was not
available. Decisions below are the ones a reader would otherwise have to rediscover.

## Shape

- **One script with inline dependencies, no nested `pyproject.toml`.** The house layout forbids
  a topic folder growing its own environment, and a single `uv run console.py` is also the
  easiest thing to drop onto a locked-down laptop. Tests pass their dependencies with `--with`.
- **A hub of background collectors, cards that only read.** Each source is polled once on an
  app-wide timer whatever the number of open windows; cards redraw from the latest values.
- **Settings in `config.local.json`, state in `%LOCALAPPDATA%`.** The repo is public, so the
  user's cities, name, apps and saved layouts never touch it.
- **Port 9001, loopback only.** The 9000s are the control-panel band; 9000 is the PM2 panel on
  this machine. Binding beyond 127.0.0.1 would expose power settings and app launching.

## Performance decisions (measured, not guessed)

- **Process sampling.** psutil took 2.4–3.0s per pass over 392 processes because protected
  processes fall back to a whole-system enumeration each. Two passes every 2s kept a core busy
  and stretched a 9s log scan to 272s. `sources/procs.py` reads every process in one
  `NtQuerySystemInformation(SystemProcessInformation)` call: 18ms. App and service matching
  reuse that snapshot and read command lines only for interpreters.
- **Claude log scan.** 1,903 files, 1.6 GB. A cold scan took 42s; a byte-level pre-filter (only
  assistant lines carrying usage are JSON-parsed) cut it to 9s, and progress is cached in
  `%LOCALAPPDATA%` keyed to a hash of `pricing.json`, so a restart costs ~2s.
- **Tasks render the first 25 of each group** with a "Show all" link. 195 rows inline made the
  page 376 KB and five seconds to serve.

## Behaviour decisions

- **Spend is an API-equivalent estimate.** Pricing is per model by longest id prefix, with
  separate 5-minute and 1-hour cache-write rates and a fast-mode multiplier. A subscription is
  flat-rate; the card says so.
- **Limits come from the endpoint Claude Code's /usage view reads**, with the stored OAuth token.
  If the token is missing or expired the card says so and estimates the 5-hour window from the
  logs (windows start on the hour of the first message after the last window closed). The
  response shape (`five_hour` / `seven_day` with `utilization` and `resets_at`) is unverified:
  the token on the build machine had expired.
- **Hotstrings: one JSON source, generated script.** Text hotstrings are plain text and escaped
  by the generator (`!` would otherwise send Alt). Prompts paste through the clipboard, which
  restores afterwards, because typing a paragraph key by key is slow and app-dependent.
- **Hotkey mechanics follow the existing master AutoHotkey script**: Win+B sends Ctrl+N in
  Claude.exe and Ctrl+Alt+F13 in VS Code; Win+G types /clear, after focusing the Claude Code
  input with Ctrl+Alt+F14 in VS Code. The F13/F14 bindings need matching VS Code keybindings
  (`claude-vscode.newConversation`, `claude-vscode.focus`).
- **Quick add parses locally**, then calls Todoist's REST create with explicit fields, so the
  `due:fri` and `+Owner` forms work the same for Todoist and the local list. `+Owner` files the
  task under the project section of that name, else adds a label: the screenshot's second chip
  (for example a meeting or a person) read as a Todoist section.
- **Window layouts** are saved per executable and title with `GetWindowPlacement`, so maximised
  and minimised states survive, and restored by executable, preferring the same title.
