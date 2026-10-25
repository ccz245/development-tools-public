"""Tasks: Todoist (or the local list) by priority, date, project or waiting, with quick add.

Drag a task onto another priority group to change its priority. The circle completes it.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from nicegui import run, ui

from ...config import expand
from ...sources.tasks import Task, export_notes, import_notes, parse_quick_add

PRIORITY_NAMES = {1: "P1 Urgent", 2: "P2 High", 3: "P3 Medium", 4: "P4 None"}
PRIORITY_COLORS = {1: "var(--wc-bad)", 2: "var(--wc-p2)", 3: "var(--wc-accent-strong)", 4: "var(--wc-muted)"}
TABS = ["Priority", "Today", "Upcoming", "Projects", "Waiting"]
GROUP_LIMIT = 25


def build(ctx, right) -> None:
    hub = ctx.hub
    settings = ctx.config["tasks"]
    waiting_label = settings.get("waiting_label", "waiting").lower()
    view = {"tab": "Priority", "query": "", "dragging": None, "done": set(), "version": -1, "expanded": set()}

    with right:
        summary = ui.label("").classes("wc-tiny")

    with ui.row().classes("w-full items-center no-wrap gap-2"):
        ui.toggle(TABS, value="Priority", on_change=lambda e: (view.update(tab=e.value), body.refresh())).props(
            "dense no-caps size=sm toggle-color=primary"
        )
        ui.space()
        search = ui.input(placeholder="Search", on_change=lambda e: (view.update(query=(e.value or "").lower()), body.refresh())).props(
            "dense outlined clearable"
        ).classes("w-48")
        with search.add_slot("prepend"):
            ui.icon("search").classes("text-sm")
        ui.button("Import notes", icon="file_download", on_click=lambda: notes_dialog("import")).props("flat dense size=sm no-caps").classes("wc-btn")
        ui.button("Update notes", icon="file_upload", on_click=lambda: notes_dialog("export")).props("flat dense size=sm no-caps").classes("wc-btn")

    quick = ui.input(placeholder="Add a task:  Title p1 #project @label +Owner due:fri").props("dense outlined").classes("w-full")
    with quick.add_slot("prepend"):
        ui.icon("add")
    status = ui.label("").classes("wc-tiny wc-muted")

    async def add_task() -> None:
        text = (quick.value or "").strip()
        if not text:
            return
        parsed = parse_quick_add(text)
        if not parsed.content:
            ui.notify("A task needs a title", type="warning")
            return
        try:
            await run.io_bound(hub.provider.add, parsed)
        except Exception as error:
            ui.notify(f"Could not add the task: {error}", type="negative")
            return
        quick.set_value("")
        ui.notify(f"Added to {hub.provider.name}: {parsed.content}", type="positive")
        await hub.collect_tasks()

    quick.on("keydown.enter", add_task)

    async def complete(task: Task) -> None:
        view["done"].add(task.id)
        body.refresh()
        try:
            await run.io_bound(hub.provider.complete, task.id)
        except Exception as error:
            view["done"].discard(task.id)
            ui.notify(f"Could not complete the task: {error}", type="negative")
        await hub.collect_tasks()

    async def move_to(priority: int) -> None:
        task_id = view["dragging"]
        view["dragging"] = None
        task = next((t for t in hub.tasks if t.id == task_id), None)
        if not task or task.priority == priority:
            return
        task.priority = priority  # optimistic; the next collection confirms it
        body.refresh()
        try:
            await run.io_bound(hub.provider.set_priority, task.id, priority)
        except Exception as error:
            ui.notify(f"Could not change the priority: {error}", type="negative")
        await hub.collect_tasks()

    def visible() -> list[Task]:
        query = view["query"]
        tasks = list(hub.tasks)  # just-completed tasks stay, struck through, until the next collection
        if query:
            tasks = [t for t in tasks if query in " ".join([t.content, t.project, t.section, *t.labels]).lower()]
        return tasks

    def task_row(task: Task) -> None:
        done = task.id in view["done"]
        today = date.today()
        with ui.row().classes("w-full no-wrap items-start gap-2 wc-task" + (" wc-task-done" if done else "")) as row:
            ui.button(icon="check_circle" if done else "radio_button_unchecked", on_click=lambda t=task: complete(t)).props(
                "flat dense round size=sm"
            ).style(f"color: {PRIORITY_COLORS[task.priority]}").tooltip("Complete")
            with ui.column().classes("gap-0 grow min-w-0"):
                ui.label(task.content).classes("wc-small font-medium")
                with ui.row().classes("gap-3 wc-tiny wc-muted items-center"):
                    if task.project:
                        ui.label(f"# {task.project}")
                    if task.section:
                        with ui.row().classes("items-center gap-1 no-wrap"):
                            ui.icon("view_agenda").classes("text-xs")
                            ui.label(task.section)
                    for label in task.labels:
                        ui.label(f"@{label}")
                    if task.due_date:
                        late = task.due_date < today
                        with ui.row().classes("items-center gap-1 no-wrap").style("color: var(--wc-bad)" if late else ""):
                            ui.icon("event").classes("text-xs")
                            ui.label("Today" if task.due_date == today else f"{task.due_date:%a %d %b}")
        if not done:
            row.props("draggable").classes("cursor-grab")
            row.on("dragstart", lambda t=task: view.update(dragging=t.id))

    def group(title: str, tasks: list[Task], color: str = "var(--wc-muted)", priority: int | None = None) -> None:
        with ui.column().classes("w-full gap-0") as box:
            with ui.row().classes("items-center gap-2 mt-1"):
                ui.label(title).classes("wc-section").style(f"color: {color}")
                ui.label(str(len(tasks))).classes("wc-tiny wc-muted")
            if tasks:
                # Long groups render their head only; hundreds of rows make every refresh slow.
                limit = None if title in view["expanded"] else GROUP_LIMIT
                for task in tasks[:limit]:
                    task_row(task)
                if limit and len(tasks) > limit:
                    ui.button(f"Show all {len(tasks)}", on_click=lambda t=title: (view["expanded"].add(t), body.refresh())).props(
                        "flat dense size=sm no-caps"
                    ).classes("wc-btn")
            elif priority is not None:
                ui.label("Drop tasks here").classes("wc-tiny wc-muted wc-drop-zone w-full")
        if priority is not None:
            async def drop() -> None:
                box.classes(remove="wc-group-drop")
                await move_to(priority)

            box.on("dragover.prevent", lambda: box.classes(add="wc-group-drop"))
            box.on("dragleave", lambda: box.classes(remove="wc-group-drop"))
            box.on("drop", drop)

    def by_due(tasks: list[Task]) -> list[Task]:
        return sorted(tasks, key=lambda t: (t.due or "9999", t.priority))

    @ui.refreshable
    def body() -> None:
        tasks = visible()
        today = date.today()
        tab = view["tab"]
        if hub.tasks_error:
            ui.label(hub.tasks_error).classes("wc-tiny").style("color: var(--wc-bad)")
        if tab == "Priority":
            for priority in (1, 2, 3, 4):
                group(PRIORITY_NAMES[priority], [t for t in tasks if t.priority == priority], PRIORITY_COLORS[priority], priority)
        elif tab == "Today":
            group("Overdue", by_due([t for t in tasks if t.due_date and t.due_date < today]), "var(--wc-bad)")
            group("Today", sorted([t for t in tasks if t.due_date == today], key=lambda t: t.priority), "var(--wc-accent-strong)")
        elif tab == "Upcoming":
            days: dict[date, list[Task]] = defaultdict(list)
            for task in tasks:
                if task.due_date and today < task.due_date <= today + timedelta(days=14):
                    days[task.due_date].append(task)
            if not days:
                ui.label("Nothing due in the next two weeks").classes("wc-small wc-muted")
            for day in sorted(days):
                group(f"{day:%a %d %b}", sorted(days[day], key=lambda t: t.priority))
        elif tab == "Projects":
            projects: dict[str, list[Task]] = defaultdict(list)
            for task in tasks:
                projects[task.project or "No project"].append(task)
            for name in sorted(projects):
                group(name, sorted(projects[name], key=lambda t: (t.priority, t.section)))
        elif tab == "Waiting":
            group("Waiting", by_due([t for t in tasks if waiting_label in (l.lower() for l in t.labels)]))

    with ui.scroll_area().classes("w-full h-[520px]"):
        body()

    def refresh() -> None:
        today = date.today()
        open_tasks = [t for t in hub.tasks if t.id not in view["done"]]
        due = sum(1 for t in open_tasks if t.due_date and t.due_date <= today)
        summary.set_text(f"{due} today · {len(open_tasks)} open")
        status.set_text(f"Source: {hub.provider.name}")
        if hub.tasks_version != view["version"] and view["dragging"] is None:
            view["version"] = hub.tasks_version
            view["done"] = {i for i in view["done"] if any(t.id == i for t in hub.tasks)}
            body.refresh()

    def notes_dialog(mode: str) -> None:
        default = settings.get("notes_file", "~/Documents/console-tasks.md")
        with ui.dialog() as dialog, ui.card().classes("w-[520px]"):
            if mode == "import":
                ui.label("Import notes").classes("wc-title")
                ui.label("Adds every open '- [ ] ...' line in a markdown file as a task. Quick-add syntax works on each line.").classes("wc-small wc-muted")
            else:
                ui.label("Update notes").classes("wc-title")
                ui.label("Writes the open tasks to a markdown file, grouped by project, replacing its contents.").classes("wc-small wc-muted")
            path = ui.input("Markdown file", value=default).props("dense outlined").classes("w-full")

            async def go() -> None:
                target = expand(path.value)
                if mode == "import":
                    lines = await run.io_bound(import_notes, target)
                    if not lines:
                        ui.notify(f"No open items found in {target}", type="warning")
                        return
                    for line in lines:
                        await run.io_bound(hub.provider.add, parse_quick_add(line))
                    ui.notify(f"Imported {len(lines)} tasks", type="positive")
                    await hub.collect_tasks()
                else:
                    await run.io_bound(export_notes, target, hub.tasks)
                    ui.notify(f"Wrote {len(hub.tasks)} tasks to {target}", type="positive")
                dialog.close()

            with ui.row().classes("w-full justify-end"):
                ui.button("Cancel", on_click=dialog.close).props("flat no-caps")
                ui.button("Import" if mode == "import" else "Write file", on_click=go).props("no-caps")
        dialog.open()

    ui.timer(1.0, refresh)
