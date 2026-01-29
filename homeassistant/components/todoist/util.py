"""Utility functions for the Todoist integration."""

from __future__ import annotations

from datetime import date, datetime

from todoist_api_python.models import Due

from homeassistant.util import dt as dt_util


def parse_due_date(task_due: Due | None) -> date | datetime | None:
    """Parse due date from Todoist task due object.

    The due.date field contains either a date object (for date-only tasks)
    or a datetime object (for tasks with a specific time). When deserialized
    from the API via from_dict(), these are already proper Python date/datetime
    objects.

    Args:
        task_due: The Due object from a Todoist task, or None.

    Returns:
        A date object for date-only due dates, a localized datetime for
        datetime due dates, or None if no due date is set.

    """
    if task_due is None or not (due_date := task_due.date):
        return None

    if isinstance(due_date, datetime):
        return dt_util.as_local(due_date)
    if isinstance(due_date, date):
        return due_date
    return None
