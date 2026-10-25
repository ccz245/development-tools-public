# development-tools-public

Portable development tooling: dashboards, small GUI and React apps, and helpers for
working with multiple coding agents. Built to run on locked-down machines where you cannot
install much — most tools are a short prompt plus a few kilobytes of starter code.

## Getting it

```bash
git clone https://github.com/ccz245/development-tools-public.git
```

Or open a tool's files on GitHub and copy them. Pin to a release tag rather than `main`, so
you know which version you are running.

## Tools

| Folder | What it is |
|---|---|
| [nicegui-windows-console](nicegui-windows-console/README.md) | One-window dashboard for a Windows dev laptop: Claude usage, power, machine load, world clocks, tasks, transcripts, hotstrings, launchpad. `uv run console.py` |

## Structure

```
README.md  AGENTS.md  CLAUDE.md  DESIGN.md  TODO.md  CHANGELOG.md
nicegui-windows-console/   one folder per tool
```
