"""Utility functions for Habitica."""

from __future__ import annotations

import datetime
from math import floor
from typing import TYPE_CHECKING, Any

from dateutil.rrule import (
    DAILY,
    FR,
    MO,
    MONTHLY,
    SA,
    SU,
    TH,
    TU,
    WE,
    WEEKLY,
    YEARLY,
    rrule,
)

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


FREQUENCY_MAP = {"daily": DAILY, "weekly": WEEKLY, "monthly": MONTHLY, "yearly": YEARLY}
WEEKDAY_MAP = {"m": MO, "t": TU, "w": WE, "th": TH, "f": FR, "s": SA, "su": SU}


def build_rrule(task: dict[str, Any]) -> rrule:
    """Build rrule string."""

    rrule_frequency = FREQUENCY_MAP.get(task["frequency"], DAILY)
    weekdays = [
        WEEKDAY_MAP[day] for day, is_active in task["repeat"].items() if is_active
    ]
    bymonthday = (
        task["daysOfMonth"]
        if rrule_frequency == MONTHLY and task["daysOfMonth"]
        else None
    )

    bysetpos = None
    if rrule_frequency == MONTHLY and task["weeksOfMonth"]:
        bysetpos = task["weeksOfMonth"]
        weekdays = weekdays if weekdays else [MO]

    return rrule(
        freq=rrule_frequency,
        interval=task["everyX"],
        dtstart=dt_util.start_of_local_day(
            datetime.datetime.fromisoformat(task["startDate"])
        ),
        byweekday=weekdays if rrule_frequency in [WEEKLY, MONTHLY] else None,
        bymonthday=bymonthday,
        bysetpos=bysetpos,
    )


def get_recurrence_rule(recurrence: rrule) -> str:
    r"""Extract and return the recurrence rule portion of an RRULE.

    This function takes an RRULE representing a task's recurrence pattern,
    builds the RRULE string, and extracts the recurrence rule part.

    'DTSTART:YYYYMMDDTHHMMSS\nRRULE:FREQ=YEARLY;INTERVAL=2'

    Parameters
    ----------
    recurrence : rrule
        An RRULE object.

    Returns
    -------
    str
        The recurrence rule portion of the RRULE string, starting with 'FREQ='.

    Example
    -------
    >>> rule = get_recurrence_rule(task)
    >>> print(rule)
    'FREQ=YEARLY;INTERVAL=2'

    """
    return str(recurrence).split("RRULE:")[1]


def get_attribute_points(
    user: dict[str, Any], content: dict[str, Any], attribute: str
) -> dict[str, float]:
    """Get modifiers contributing to strength attribute."""

    gear_set = {
        "weapon",
        "armor",
        "head",
        "shield",
        "back",
        "headAccessory",
        "eyewear",
        "body",
    }

    equipment = sum(
        stats[attribute]
        for gear in gear_set
        if (equipped := user["items"]["gear"]["equipped"].get(gear))
        and (stats := content["gear"]["flat"].get(equipped))
    )

    class_bonus = sum(
        stats[attribute] / 2
        for gear in gear_set
        if (equipped := user["items"]["gear"]["equipped"].get(gear))
        and (stats := content["gear"]["flat"].get(equipped))
        and stats["klass"] == user["stats"]["class"]
    )

    return {
        "level": min(round(user["stats"]["lvl"] / 2), 50),
        "equipment": equipment,
        "class": class_bonus,
        "allocated": user["stats"][attribute],
        "buffs": user["stats"]["buffs"][attribute],
    }


def get_attributes_total(
    user: dict[str, Any], content: dict[str, Any], attribute: str
) -> int:
    """Get total attribute points."""
    return floor(
        sum(value for value in get_attribute_points(user, content, attribute).values())
    )
