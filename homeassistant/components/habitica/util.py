"""Utility functions for Habitica."""

from __future__ import annotations

from dataclasses import fields
import datetime
from math import floor
from typing import TYPE_CHECKING

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
from habiticalib import ContentData, Frequency, TaskData, UserData

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


def next_due_date(task: TaskData, today: datetime.datetime) -> datetime.date | None:
    """Calculate due date for dailies and yesterdailies."""

    if task.everyX == 0 or not task.nextDue:  # grey dailies never become due
        return None

    if TYPE_CHECKING:
        assert task.startDate

    if task.isDue is True and not task.completed:
        return dt_util.as_local(today).date()

    if task.startDate > today:
        if task.frequency is Frequency.DAILY or (
            task.frequency in (Frequency.MONTHLY, Frequency.YEARLY) and task.daysOfMonth
        ):
            return dt_util.as_local(task.startDate).date()

        if (
            task.frequency in (Frequency.WEEKLY, Frequency.MONTHLY)
            and (nextdue := task.nextDue[0])
            and task.startDate > nextdue
        ):
            return dt_util.as_local(task.nextDue[1]).date()

    return dt_util.as_local(task.nextDue[0]).date()


def entity_used_in(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Get list of related automations and scripts."""
    used_in = automations_with_entity(hass, entity_id)
    used_in += scripts_with_entity(hass, entity_id)
    return used_in


FREQUENCY_MAP = {"daily": DAILY, "weekly": WEEKLY, "monthly": MONTHLY, "yearly": YEARLY}
WEEKDAY_MAP = {"m": MO, "t": TU, "w": WE, "th": TH, "f": FR, "s": SA, "su": SU}


def build_rrule(task: TaskData) -> rrule:
    """Build rrule string."""

    if TYPE_CHECKING:
        assert task.frequency
        assert task.everyX
    rrule_frequency = FREQUENCY_MAP.get(task.frequency, DAILY)
    weekdays = [day for key, day in WEEKDAY_MAP.items() if getattr(task.repeat, key)]
    bymonthday = (
        task.daysOfMonth if rrule_frequency == MONTHLY and task.daysOfMonth else None
    )

    bysetpos = None
    if rrule_frequency == MONTHLY and task.weeksOfMonth:
        bysetpos = task.weeksOfMonth
        weekdays = weekdays if weekdays else [MO]

    return rrule(
        freq=rrule_frequency,
        interval=task.everyX,
        dtstart=dt_util.start_of_local_day(task.startDate),
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
    user: UserData, content: ContentData, attribute: str
) -> dict[str, float]:
    """Get modifiers contributing to STR/INT/CON/PER attributes."""

    equipment = sum(
        getattr(stats, attribute)
        for gear in fields(user.items.gear.equipped)
        if (equipped := getattr(user.items.gear.equipped, gear.name))
        and (stats := content.gear.flat[equipped])
    )

    class_bonus = sum(
        getattr(stats, attribute) / 2
        for gear in fields(user.items.gear.equipped)
        if (equipped := getattr(user.items.gear.equipped, gear.name))
        and (stats := content.gear.flat[equipped])
        and stats.klass == user.stats.Class
    )
    if TYPE_CHECKING:
        assert user.stats.lvl

    return {
        "level": min(floor(user.stats.lvl / 2), 50),
        "equipment": equipment,
        "class": class_bonus,
        "allocated": getattr(user.stats, attribute),
        "buffs": getattr(user.stats.buffs, attribute),
    }


def get_attributes_total(user: UserData, content: ContentData, attribute: str) -> int:
    """Get total attribute points."""
    return floor(
        sum(value for value in get_attribute_points(user, content, attribute).values())
    )


def inventory_list(
    user: UserData, content: ContentData, item_type: str
) -> dict[str, int]:
    """List inventory items of given type."""
    return {
        getattr(content, item_type)[k].text: v
        for k, v in getattr(user.items, item_type, {}).items()
        if k != "Saddle"
    }
