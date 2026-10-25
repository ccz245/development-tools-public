# AGENTS.md — start here

Public repo of portable development tooling. Anyone can read it, and it is cloned or copied
onto machines outside this one.

## Structure

```
README.md  AGENTS.md  CLAUDE.md  DESIGN.md  TODO.md  CHANGELOG.md
```

## Rules

- **Public: never commit client names, client email addresses, client data, secrets, or
  credentials** — not in code, docs, commit messages, or issues. Per-environment config
  lives in a git-ignored `*.local.*` file. Secrets live in Doppler.
- **Commit as the GitHub noreply address**, never a personal email. This repo's
  `user.email` is set locally; check it before committing from a new clone.
- **Keep tools small and portable:** a prompt plus minimal starter code where possible. No
  hardcoded paths to `~/Development/` or other repos, no admin rights, no native
  dependencies, no network calls beyond what is configured.
- **Version every tool.** Bump the version in the tool and add a `CHANGELOG.md` entry, so a
  copy on another machine can say which version it is.
