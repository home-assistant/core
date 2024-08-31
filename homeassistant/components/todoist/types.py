"""Types for the Todoist component."""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict


class DueDate(TypedDict):
    """Dict representing a due date in a todoist api response."""

    date: str
    is_recurring: bool
    lang: str
    string: str
    timezone: str | None


class ProjectData(TypedDict):
    """Dict representing project data."""

    name: str
    id: str | None


class CustomProject(TypedDict):
    """Dict representing a custom project."""

    name: str
    due_date_days: int | None
    include_projects: list[str] | None
    labels: list[str] | None


class CalData(TypedDict, total=False):
    """Dict representing calendar data in todoist."""

    all_tasks: list[str]


class TodoistEvent(TypedDict):
    """Dict representing a todoist event."""

    all_day: bool
    completed: bool
    description: str
    due_today: bool
    end: datetime | None
    labels: list[str]
    overdue: bool
    priority: int
    start: datetime
    summary: str
