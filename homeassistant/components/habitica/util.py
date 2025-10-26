"""Utility functions for Habitica."""

from __future__ import annotations

from dataclasses import asdict, fields
import datetime
from math import floor
from typing import TYPE_CHECKING, Any, Literal

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
from habiticalib import ContentData, Frequency, GroupData, QuestBoss, TaskData, UserData

from homeassistant.util import dt as dt_util


def next_due_date(task: TaskData, today: datetime.datetime) -> datetime.date | None:
    """Calculate due date for dailies and yesterdailies."""

    if task.everyX == 0 or not task.nextDue:  # grey dailies never become due
        return None
    if task.frequency is Frequency.WEEKLY and not any(asdict(task.repeat).values()):
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


FREQUENCY_MAP: dict[str, Literal[0, 1, 2, 3]] = {
    "daily": DAILY,
    "weekly": WEEKLY,
    "monthly": MONTHLY,
    "yearly": YEARLY,
}
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
        bysetpos = [i + 1 for i in task.weeksOfMonth]
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

    Args:
        recurrence: An RRULE object.

    Returns:
        The recurrence rule portion of the RRULE string, starting with 'FREQ='.

    Example:
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


def pending_quest_items(user: UserData, content: ContentData) -> int | None:
    """Pending quest items."""

    return (
        user.party.quest.progress.collectedItems
        if user.party.quest.key
        and content.quests[user.party.quest.key].collect is not None
        else None
    )


def pending_damage(user: UserData, content: ContentData) -> float | None:
    """Pending damage."""

    return (
        user.party.quest.progress.up
        if user.party.quest.key
        and content.quests[user.party.quest.key].boss is not None
        else None
    )


def quest_attributes(party: GroupData, content: ContentData) -> dict[str, Any]:
    """Quest description."""
    return {
        "quest_details": content.quests[party.quest.key].notes
        if party.quest.key
        else None,
        "quest_participants": f"{sum(x is True for x in party.quest.members.values())} / {party.memberCount}",
    }


def rage_attributes(party: GroupData, content: ContentData) -> dict[str, Any]:
    """Display name of rage skill and description of it's effect in attributes."""
    boss = quest_boss(party, content)
    return {
        "rage_skill": boss.rage.title if boss and boss.rage else None,
        "effect": boss.rage.effect if boss and boss.rage else None,
    }


def quest_boss(party: GroupData, content: ContentData) -> QuestBoss | None:
    """Quest boss."""

    return content.quests[party.quest.key].boss if party.quest.key else None


def collected_quest_items(party: GroupData, content: ContentData) -> dict[str, Any]:
    """List collected quest items."""

    return (
        {
            collect[k].text: f"{v} / {collect[k].count}"
            for k, v in party.quest.progress.collect.items()
        }
        if party.quest.key and (collect := content.quests[party.quest.key].collect)
        else {}
    )
