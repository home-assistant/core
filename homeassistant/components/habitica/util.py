"""Utility functions for Habitica."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


def next_due_date(task: dict[str, Any], last_cron: str) -> datetime.date | None:
    """Calculate due date for dailies and yesterdailies."""

    if task["everyX"] == 0 or not task.get("nextDue"):  # grey dailies never become due
        return None

    today = to_date(last_cron)
    startdate = to_date(task["startDate"])
    if TYPE_CHECKING:
        assert today
        assert startdate

    if task["isDue"] and not task["completed"]:
        return to_date(last_cron)

    if startdate > today:
        if task["frequency"] == "daily" or (
            task["frequency"] in ("monthly", "yearly") and task["daysOfMonth"]
        ):
            return startdate

        if (
            task["frequency"] in ("weekly", "monthly")
            and (nextdue := to_date(task["nextDue"][0]))
            and startdate > nextdue
        ):
            return to_date(task["nextDue"][1])

    return to_date(task["nextDue"][0])


def to_date(date: str) -> datetime.date | None:
    """Convert an iso date to a datetime.date object."""
    try:
        return dt_util.as_local(datetime.datetime.fromisoformat(date)).date()
    except ValueError:
        # sometimes nextDue dates are JavaScript datetime strings instead of iso:
        # "Mon May 06 2024 00:00:00 GMT+0200"
        try:
            return dt_util.as_local(
                datetime.datetime.strptime(date, "%a %b %d %Y %H:%M:%S %Z%z")
            ).date()
        except ValueError:
            return None


def entity_used_in(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Get list of related automations and scripts."""
    used_in = automations_with_entity(hass, entity_id)
    used_in += scripts_with_entity(hass, entity_id)
    return used_in
