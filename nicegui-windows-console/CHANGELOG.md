# Changelog

## 2026-10-24

- Rebuilt the console from a screenshot: eight cards (Claude usage, idle and power, this
  machine, world clocks, tasks, transcripts, hotstrings, launchpad), draggable and hideable,
  dark and light themes, native window, `--demo` mode, 25 tests.
- Process sampling moved to a single `NtQuerySystemInformation` snapshot (2.5s to 18ms per pass).
- Claude log scan pre-filtered and cached (cold 42s to 9s; restart ~2s).
- Fixed: the power card wrote the current timeouts back to Windows on page load (values were
  unchanged, verified); side effects are now guarded synchronously.
