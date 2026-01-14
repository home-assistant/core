"""Utility functions for the Todoist integration."""

from __future__ import annotations

from datetime import date, datetime

from todoist_api_python.models import Due

from homeassistant.util import dt as dt_util


def parse_due_date(task_due: Due | None) -> date | datetime | None:
    """Parse due date from Todoist task due object.

    The due.date field contains either a date string (YYYY-MM-DD)
    or a datetime string (ISO format with time component).

    Args:
        task_due: The Due object from a Todoist task, or None.

    Returns:
        A date object for date-only due dates, a localized datetime for
        datetime due dates, or None if no due date is set.

    """
    if task_due is None or not task_due.date:
        return None
    date_str = str(task_due.date)
    # Date-only strings are exactly 10 chars (YYYY-MM-DD)
    if len(date_str) == 10:
        return dt_util.parse_date(date_str)
    # Parse as datetime
    parsed_dt = dt_util.parse_datetime(date_str)
    if parsed_dt:
        return dt_util.as_local(parsed_dt)
    return None
