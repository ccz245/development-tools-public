"""Dictation transcripts written by a separate speech-to-text service.

Whether the service is running is answered by procs.find, like any other app.

Reads JSONL, one transcript per line, from a file or every *.jsonl in a folder. Field names
vary between dictation tools, so several common spellings are accepted:
  time:  ts | timestamp | time | created_at   (ISO string or epoch seconds)
  text:  text | transcript | content
  two durations shown as "a + b" seconds, e.g. speech-to-text then clean-up:
         stt_s | transcribe_s | asr_s   and   post_s | cleanup_s | llm_s
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

TIME_KEYS = ("ts", "timestamp", "time", "created_at")
TEXT_KEYS = ("text", "transcript", "content")
FIRST_KEYS = ("stt_s", "transcribe_s", "asr_s")
SECOND_KEYS = ("post_s", "cleanup_s", "llm_s")


@dataclass
class Transcript:
    ts: datetime  # local, naive
    text: str
    first: float | None = None
    second: float | None = None


def _pick(row: dict, keys: tuple[str, ...]):
    return next((row[k] for k in keys if row.get(k) is not None), None)


def _parse_time(value) -> datetime | None:
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value)
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return stamp.astimezone().replace(tzinfo=None) if stamp.tzinfo else stamp
    except (ValueError, OSError, OverflowError):
        return None


def parse_row(row: dict) -> Transcript | None:
    ts = _parse_time(_pick(row, TIME_KEYS))
    text = _pick(row, TEXT_KEYS)
    if ts is None or not text:
        return None
    first, second = _pick(row, FIRST_KEYS), _pick(row, SECOND_KEYS)
    return Transcript(ts, str(text).strip(), float(first) if first is not None else None, float(second) if second is not None else None)


class TranscriptStore:
    """Re-reads only when a file's modification time changes."""

    def __init__(self, path: Path | None):
        self.path = path
        self._stamp: tuple = ()
        self.items: list[Transcript] = []

    def _files(self) -> list[Path]:
        if not self.path or not self.path.exists():
            return []
        return sorted(self.path.glob("*.jsonl")) if self.path.is_dir() else [self.path]

    def load(self) -> list[Transcript]:
        files = self._files()
        stamp = tuple((f, f.stat().st_mtime_ns) for f in files)
        if stamp == self._stamp:
            return self.items
        items = []
        for file in files:
            for line in file.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict) and (item := parse_row(row)):
                    items.append(item)
        self.items = sorted(items, key=lambda t: t.ts, reverse=True)
        self._stamp = stamp
        return self.items
