"""Types for the Todoist component."""
from __future__ import annotations

from typing import TypedDict


class DueDate(TypedDict):
    """Dict representing a due date in a todoist api response."""

    date: str
    is_recurring: bool
    lang: str
    string: str
    timezone: str | None
