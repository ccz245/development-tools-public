# Changelog

## 2026-10-25

- Added `nicegui-windows-console/`, the first tool (see its own CHANGELOG), and
  `.claude/launch.json` to preview it.
- Fixed the commit guard flagging CLAUDE.md's `@AGENTS.md` pointer as an email address: it
  scanned diff lines with their leading `+`.
- Added a `commit-msg` hook that blocks personal author emails, real email addresses and
  denylisted terms; setup steps in `AGENTS.md`.
- Created the repo, public from the first commit.
