"""Filtering helpers for Todoist tasks."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date

from todoist_api_python.models import Task


def _matches_labels(task: Task, labels: Sequence[str] | None) -> bool:
    """Return True if task matches the given label filter.

    If labels is None or empty, no label filtering is applied.
    """
    if not labels:
        return True

    task_labels = getattr(task, "labels", None) or []
    return any(lbl in task_labels for lbl in labels)


def _matches_priorities(task: Task, priorities: Sequence[int] | None) -> bool:
    """Return True if task matches the given priority filter.

    If priorities is None or empty, no priority filtering is applied.
    """
    if not priorities:
        return True

    task_priority = getattr(task, "priority", None)
    return task_priority in priorities


def _matches_due_range(
    task: Task,
    start: date | None,
    end: date | None,
) -> bool:
    """Return True if task's due date is within [start, end].

    If both start and end are None, no due-date filtering is applied.
    """
    if start is None and end is None:
        return True

    due = getattr(task, "due", None)
    if due is None or getattr(due, "date", None) is None:
        return False

    due_value = due.date
    if isinstance(due_value, str):
        try:
            due_date = date.fromisoformat(due_value)
        except ValueError:
            return False
    elif isinstance(due_value, date):
        due_date = due_value
    else:
        return False

    if start is not None and due_date < start:
        return False
    if end is not None and due_date > end:
        return False

    return True


def filter_tasks(
    tasks: Iterable[Task],
    labels: Sequence[str] | None = None,
    priorities: Sequence[int] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[Task]:
    """Return a list of tasks that match all active filters.

    - labels: keep tasks that have at least one of these labels
    - priorities: keep tasks whose priority is in this list
    - start_date/end_date: keep tasks whose due date is within the range
    """
    filtered: list[Task] = []

    for task in tasks:
        if not _matches_labels(task, labels):
            continue
        if not _matches_priorities(task, priorities):
            continue
        if not _matches_due_range(task, start_date, end_date):
            continue

        filtered.append(task)

    return filtered
