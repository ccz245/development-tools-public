"""Tasks, from Todoist when a token is configured, otherwise from a local JSON file.

Priorities use Todoist's on-screen numbering throughout this module: 1 is urgent (P1) and 4 is
none (P4). The Todoist API stores them the other way round (4 = P1), so the Todoist provider
converts at its edge and nothing else needs to know.

Quick add takes `Title p1 #project @label +Owner due:fri`. `+Owner` files the task under the
project section of that name when one exists, otherwise adds it as a label.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Protocol

import httpx

TODOIST_API = "https://api.todoist.com/api/v1"
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


@dataclass
class Task:
    id: str
    content: str
    priority: int = 4  # 1 = P1 urgent ... 4 = P4 none
    project: str = ""
    section: str = ""
    labels: list[str] = field(default_factory=list)
    due: str | None = None  # ISO date
    description: str = ""

    @property
    def due_date(self) -> date | None:
        return date.fromisoformat(self.due[:10]) if self.due else None


@dataclass
class QuickAdd:
    content: str
    priority: int = 4
    project: str | None = None
    labels: list[str] = field(default_factory=list)
    owner: str | None = None
    due: str | None = None  # as typed, e.g. "fri" or "2026-11-02"


_TOKEN = r'(?:"([^"]+)"|(\S+))'  # a quoted phrase or one word


def parse_quick_add(text: str) -> QuickAdd:
    result = QuickAdd(content="")

    def take(pattern: str, handle) -> None:
        nonlocal text
        def replace(match: re.Match) -> str:
            handle(next(g for g in match.groups() if g is not None))
            return " "
        text = re.sub(pattern, replace, text)

    take(r"(?<!\S)p([1-4])(?!\S)", lambda v: setattr(result, "priority", int(v)))
    take(r"(?<!\S)due:" + _TOKEN, lambda v: setattr(result, "due", v))
    take(r"(?<!\S)#" + _TOKEN, lambda v: setattr(result, "project", v.replace("_", " ")))
    take(r"(?<!\S)@" + _TOKEN, lambda v: result.labels.append(v))
    take(r"(?<!\S)\+" + _TOKEN, lambda v: setattr(result, "owner", v.replace("_", " ")))
    result.content = " ".join(text.split())
    return result


def resolve_due(value: str | None, today: date | None = None) -> str | None:
    """Turn a typed due value into an ISO date where it is simple enough to do locally."""
    if not value:
        return None
    today = today or date.today()
    word = value.lower()
    if word in ("today", "tod"):
        return today.isoformat()
    if word in ("tomorrow", "tom", "tmr"):
        return (today + timedelta(days=1)).isoformat()
    if word[:3] in WEEKDAYS:
        ahead = (WEEKDAYS.index(word[:3]) - today.weekday()) % 7 or 7
        return (today + timedelta(days=ahead)).isoformat()
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


class Provider(Protocol):
    name: str

    def list(self) -> list[Task]: ...
    def add(self, quick: QuickAdd) -> Task: ...
    def complete(self, task_id: str) -> None: ...
    def set_priority(self, task_id: str, priority: int) -> None: ...


class LocalProvider:
    """Tasks in one JSON file. Used when no Todoist token is set, and for demo mode."""

    name = "Local"

    def __init__(self, path: Path):
        self.path = path

    def _read(self) -> list[Task]:
        if not self.path.exists():
            return []
        return [Task(**row) for row in json.loads(self.path.read_text(encoding="utf-8"))]

    def _write(self, tasks: list[Task]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([asdict(t) for t in tasks], indent=2), encoding="utf-8")

    def list(self) -> list[Task]:
        return self._read()

    def add(self, quick: QuickAdd) -> Task:
        tasks = self._read()
        task = Task(
            id=uuid.uuid4().hex[:12],
            content=quick.content,
            priority=quick.priority,
            project=quick.project or "Inbox",
            section=quick.owner or "",
            labels=quick.labels,
            due=resolve_due(quick.due),
        )
        tasks.append(task)
        self._write(tasks)
        return task

    def complete(self, task_id: str) -> None:
        self._write([t for t in self._read() if t.id != task_id])

    def set_priority(self, task_id: str, priority: int) -> None:
        tasks = self._read()
        for task in tasks:
            if task.id == task_id:
                task.priority = priority
        self._write(tasks)


class TodoistProvider:
    name = "Todoist"

    def __init__(self, token: str, timeout: float = 15.0):
        self._client = httpx.Client(
            base_url=TODOIST_API, headers={"Authorization": f"Bearer {token}"}, timeout=timeout
        )
        self._projects: dict[str, str] = {}
        self._sections: dict[str, tuple[str, str]] = {}  # id -> (project id, name)

    def _paged(self, path: str) -> list[dict]:
        rows, cursor = [], None
        while True:
            params = {"limit": 200, **({"cursor": cursor} if cursor else {})}
            response = self._client.get(path, params=params)
            response.raise_for_status()
            body = response.json()
            rows.extend(body.get("results", []))
            cursor = body.get("next_cursor")
            if not cursor:
                return rows

    def _refresh_names(self) -> None:
        self._projects = {p["id"]: p["name"] for p in self._paged("/projects")}
        self._sections = {s["id"]: (s["project_id"], s["name"]) for s in self._paged("/sections")}

    def list(self) -> list[Task]:
        self._refresh_names()
        tasks = []
        for row in self._paged("/tasks"):
            due = (row.get("due") or {}).get("date")
            tasks.append(Task(
                id=row["id"],
                content=row["content"],
                priority=5 - int(row.get("priority", 1)),
                project=self._projects.get(row.get("project_id"), ""),
                section=self._sections.get(row.get("section_id"), ("", ""))[1],
                labels=list(row.get("labels") or []),
                due=due,
                description=row.get("description") or "",
            ))
        return tasks

    def add(self, quick: QuickAdd) -> Task:
        if not self._projects:
            self._refresh_names()
        body: dict = {"content": quick.content, "priority": 5 - quick.priority}
        labels = list(quick.labels)
        project_id = None
        if quick.project:
            project_id = next((pid for pid, name in self._projects.items() if name.lower() == quick.project.lower()), None)
            if project_id:
                body["project_id"] = project_id
            else:
                labels.append(quick.project)  # unknown project: keep the hint rather than lose it
        if quick.owner:
            section_id = next(
                (sid for sid, (pid, name) in self._sections.items()
                 if name.lower() == quick.owner.lower() and (project_id is None or pid == project_id)),
                None,
            )
            if section_id:
                body["section_id"] = section_id
            else:
                labels.append(quick.owner)
        if labels:
            body["labels"] = labels
        if quick.due:
            body["due_string"] = quick.due
        response = self._client.post("/tasks", json=body)
        response.raise_for_status()
        row = response.json()
        return Task(id=row["id"], content=row["content"], priority=quick.priority, project=quick.project or "")

    def complete(self, task_id: str) -> None:
        self._client.post(f"/tasks/{task_id}/close").raise_for_status()

    def set_priority(self, task_id: str, priority: int) -> None:
        self._client.post(f"/tasks/{task_id}", json={"priority": 5 - priority}).raise_for_status()


def import_notes(path: Path) -> list[str]:
    """Open action items from a markdown notes file: `- [ ] ...` lines, quick-add syntax allowed."""
    if not path.exists():
        return []
    return [m.group(1).strip() for m in re.finditer(r"^\s*[-*]\s+\[ \]\s+(.+)$", path.read_text(encoding="utf-8"), flags=re.MULTILINE)]


def export_notes(path: Path, tasks: list[Task]) -> None:
    """Write open tasks to a markdown file, grouped by project then priority."""
    lines = [f"# Open tasks ({datetime.now():%Y-%m-%d %H:%M})", ""]
    for project in sorted({t.project for t in tasks}):
        lines.append(f"## {project or 'No project'}")
        for task in sorted((t for t in tasks if t.project == project), key=lambda t: (t.priority, t.due or "9999")):
            extras = " ".join(filter(None, [
                f"p{task.priority}" if task.priority < 4 else "",
                f"due:{task.due[:10]}" if task.due else "",
                *(f"@{label}" for label in task.labels),
            ]))
            lines.append(f"- [ ] {task.content}" + (f" {extras}" if extras else ""))
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
