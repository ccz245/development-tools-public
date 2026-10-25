"""The eight cards, in their default order."""

from __future__ import annotations

from ..shell import CardDef
from . import clocks, hotstrings, launchpad, machine, power, tasks, transcripts, usage

CARDS = [
    CardDef("usage", "Claude usage", "insights", usage.build, rows=2),
    CardDef("power", "Idle and power", "power_settings_new", power.build),
    CardDef("clocks", "World clocks", "schedule", clocks.build, rows=2),
    CardDef("machine", "This machine", "memory", machine.build),  # after clocks so it fills column 2
    CardDef("tasks", "Tasks", "task_alt", tasks.build, span=2),
    CardDef("transcripts", "Transcripts", "mic", transcripts.build),
    CardDef("hotstrings", "Hotstrings", "keyboard", hotstrings.build, span=2),
    CardDef("launchpad", "Launchpad", "rocket_launch", launchpad.build),
]
