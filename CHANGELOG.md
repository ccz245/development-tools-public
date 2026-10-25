# Changelog

## 2026-10-25

- Removed `nicegui-windows-console/` and `.claude/launch.json`: the original NiceGUI app,
  maintained elsewhere, is the one in use, so the rebuild is retired. The repo holds no tools
  for now.
- Added `nicegui-windows-console/`, the first tool (see its own CHANGELOG), and
  `.claude/launch.json` to preview it.
- Fixed the commit guard flagging CLAUDE.md's `@AGENTS.md` pointer as an email address: it
  scanned diff lines with their leading `+`.
- Added a `commit-msg` hook that blocks personal author emails, real email addresses and
  denylisted terms; setup steps in `AGENTS.md`.
- Created the repo, public from the first commit.
