"""Generic sample data for `--demo`, so the console can be shown anywhere without real data."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from .sources.transcripts import Transcript

APPS = [
    {"name": "Agent Fleet Manager", "command": ["notepad.exe"], "match": "explorer.exe"},
    {"name": "Note Taker", "command": ["notepad.exe"], "match": "notepad.exe"},
]


def write_tasks(path: Path) -> None:
    """(Re)write the demo task list, with due dates relative to today."""
    today = date.today()
    rows = [
        ("Propose the project timeline and the parallel-run window", 2, "Platform migration", "Kick-off meeting", None),
        ("Propose the meeting structure for the project team", 2, "Platform migration", "Kick-off meeting", None),
        ("Start the as-is walkthrough with the process owner", 2, "Platform migration", "Kick-off meeting", today),
        ("Circulate the relevant workflow components", 3, "Platform migration", "Overview session", None),
        ("Share what else can be exported besides the database", 3, "Platform migration", "Overview session", None),
        ("Export the remaining apps' settings with the admin account", 3, "Platform migration", "Overview session", today + timedelta(days=2)),
        ("Confirm what is replacing the document scanner", 3, "Platform migration", "Overview session", None),
        ("Decide whether to re-use the existing integration credentials", 3, "Platform migration", "Security", None),
        ("Check what network setup is needed (laptop, VM, jump boxes)", 3, "Platform migration", "Security", today + timedelta(days=4)),
        ("Follow up on the weekly pricing process", 3, "Data platform", "Pricing", None),
        ("Find out what else is moving to the new data platform", 3, "Data platform", "Pricing", None),
        ("Check whether the phone app needs a replacement", 4, "Platform migration", "Overview session", None),
        ("Book the architecture review", 4, "Data platform", "", today + timedelta(days=6)),
        ("Renew the test certificates", 4, "Operations", "", today - timedelta(days=1)),
        ("Waiting on access to the analytics workspace", 4, "Data platform", "", None),
    ]
    tasks = [
        {
            "id": f"demo{i:02d}",
            "content": content,
            "priority": priority,
            "project": project,
            "section": section,
            "labels": ["waiting"] if content.startswith("Waiting") else [],
            "due": due.isoformat() if due else None,
            "description": "",
        }
        for i, (content, priority, project, section, due) in enumerate(rows)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tasks, indent=2), encoding="utf-8")


def transcripts() -> list[Transcript]:
    now = datetime.now().replace(second=0, microsecond=0)
    lines = [
        (6, 0.6, 2.1, "You investigated the restore screen layout, but it's no longer working."),
        (25, 0.4, 1.8, "Below are some notes on the initial design for the replacement app."),
        (40, 0.3, 1.3, "Can you help me start up this repository? Git clone into my repo folder."),
        (55, 0.3, 1.6, "Can you check my productivity tools repo, what is that, does it have a remote?"),
        (90, 0.5, 2.4, "I was granted access to the data catalog, which has a lot of files I want to download. Can you check if you can read them?"),
        (130, 0.5, 1.5, "Can you check, Windows T seems to be not working. When I press it, one of the apps on the bottom pops up in preview mode."),
        (200, 0.5, 1.9, "This is the platform introduction. Yesterday I was granted access to the workspace apps and the catalog."),
        (320, 0.4, 1.7, "Going forward, Windows B alone will do the new chat, and Windows G will do the slash clear."),
        (330, 0.6, 3.8, "Can you check what AutoHotkey version is on this machine?"),
        (1500, 0.5, 1.8, "I'm trying to paste an image into Excel. Why doesn't it let me? I can copy into other files, just not this one."),
        (1510, 0.4, 1.4, "This message required an approval. Can we do it some other way?"),
    ]
    return [Transcript(now - timedelta(minutes=m), text, a, b) for m, a, b, text in lines]
