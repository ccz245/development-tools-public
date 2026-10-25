# AGENTS.md — start here

Public repo of portable development tooling. Anyone can read it, and it is cloned or copied
onto machines outside this one.

## Structure

```
README.md  AGENTS.md  CLAUDE.md  DESIGN.md  TODO.md  CHANGELOG.md
.githooks/commit-msg       Blocks commits carrying private details (see below)
```

Each tool is a topic folder at the root holding everything only it uses, with its own
`AGENTS.md` for what is specific to it.

## Setting up a clone you will commit from

```bash
git config user.email 11395158+ccz245@users.noreply.github.com
git config core.hooksPath .githooks
```

The hook blocks a commit when the author email is not the noreply address, when the added
lines or the message contain a real email address, or when they contain any term in
`~/.config/development-tools-public/denylist.txt` (override with `DEVTOOLS_DENYLIST`). The
denylist names clients, so it never lives in this repo; copy it to each machine by hand and
add every new client's names, domains and account names to it.

## Rules

- **Public: never commit client names, client email addresses, client data, secrets, or
  credentials** — not in code, docs, commit messages, or issues. Per-environment config
  lives in a git-ignored `*.local.*` file. Secrets live in Doppler.
- **Commit as the GitHub noreply address**, never a personal email. Never bypass the hook
  with `--no-verify`.
- **Keep tools small and portable:** a prompt plus minimal starter code where possible. No
  hardcoded paths to `~/Development/` or other repos, no admin rights, no native
  dependencies, no network calls beyond what is configured.
- **Version every tool.** Bump the version in the tool and add a `CHANGELOG.md` entry, so a
  copy on another machine can say which version it is.
