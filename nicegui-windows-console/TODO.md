# TODO

## Cross-machine actions

- [ ] On the machine with the original app: compare it with this rebuild side by side and note
      what differs (sources, wording, behaviour).
- [ ] Copy `config.local.json` to each machine that runs the console (it is git-ignored).

## Decisions to confirm (assumptions made during the rebuild)

- [ ] **Claude limits source.** The stored Claude Code token here expired ~125 days ago, so the
      limits endpoint and its response shape are untested. What did the original read?
- [ ] **Transcripts.** Where does the dictation service write, in what format, and what does
      `0.6 + 2.1` mean? Assumed: JSONL, speech-to-text seconds + clean-up seconds.
- [ ] **`+Owner` in quick add.** Assumed: a project section of that name, else a label. Could be
      a Todoist assignee in shared projects instead.
- [ ] **Import notes / Update notes.** Assumed: import open `- [ ]` lines from a markdown file;
      write open tasks back to one. What did they do originally?
- [ ] **Launchpad apps.** Commands and match strings for Agent Fleet Manager and Note Taker.
- [ ] **Win+G in Claude.exe** "wipes the composer" with Ctrl+A, Delete before /clear: confirm.
      **Win+H hibernate** is new relative to the master script.
- [ ] **One AutoHotkey script or two.** Applying the generated script while the master script
      runs binds CapsLock, Win+B and Win+G twice. Retire the master, or drop those from here.
- [ ] **Temperatures** show a dash without LibreHardwareMonitor running (or admin rights).
- [ ] **Title**: "Windows Console" (now) or "NiceGUI App" (screenshot).
- [ ] **Prompt texts** for `;rev`, `;par` and the rest were written fresh; review the wording.

## Next steps

- [ ] Publish to the repo once reviewed (committed locally, not pushed).
- [ ] Desktop shortcut or start-up entry that runs `uv run console.py` from this folder.
