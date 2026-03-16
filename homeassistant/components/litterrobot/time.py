"""Support for Litter-Robot time."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Generic

from pylitterbot import LitterRobot3, LitterRobot5

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import LitterRobotConfigEntry
from .entity import LitterRobotEntity, _WhiskerEntityT, whisker_command

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class RobotTimeEntityDescription(TimeEntityDescription, Generic[_WhiskerEntityT]):
    """A class that describes robot time entities."""

    value_fn: Callable[[_WhiskerEntityT], time | None]
    set_fn: Callable[[_WhiskerEntityT, time], Coroutine[Any, Any, bool]]


def _as_local_time(start: datetime | None) -> time | None:
    """Return a datetime as local time."""
    return dt_util.as_local(start).time() if start else None


def _get_lr5_today_schedule(robot: LitterRobot5) -> dict[str, Any] | None:
    """Get today's schedule entry from the LR5 sleep schedules.

    Reads the raw schedule data regardless of whether sleep mode is
    enabled, so that time entities always show the configured times.
    """
    schedules = robot._data.get("sleepSchedules")  # noqa: SLF001
    if isinstance(schedules, dict):
        schedules = list(schedules.values())
    if not isinstance(schedules, list) or not schedules:
        return None
    today_dow = dt_util.now().weekday()  # 0=Monday
    for entry in schedules:
        if entry.get("dayOfWeek") == today_dow:
            return entry
    return schedules[0]


def _minutes_to_time(minutes: int | None) -> time | None:
    """Convert minutes from midnight to a time object."""
    if minutes is None:
        return None
    return time(hour=minutes // 60, minute=minutes % 60)


def _lr5_sleep_start(robot: LitterRobot5) -> time | None:
    """Get the configured sleep start time for today."""
    schedule = _get_lr5_today_schedule(robot)
    if schedule is None:
        return None
    return _minutes_to_time(schedule.get("sleepTime"))


def _lr5_sleep_end(robot: LitterRobot5) -> time | None:
    """Get the configured wake time for today."""
    schedule = _get_lr5_today_schedule(robot)
    if schedule is None:
        return None
    return _minutes_to_time(schedule.get("wakeTime"))


LITTER_ROBOT_3_SLEEP_START = RobotTimeEntityDescription[LitterRobot3](
    key="sleep_mode_start_time",
    translation_key="sleep_mode_start_time",
    entity_category=EntityCategory.CONFIG,
    value_fn=lambda robot: _as_local_time(robot.sleep_mode_start_time),
    set_fn=(
        lambda robot, value: robot.set_sleep_mode(
            robot.sleep_mode_enabled,
            value.replace(tzinfo=dt_util.get_default_time_zone()),
        )
    ),
)

LITTER_ROBOT_5_TIME_ENTITIES: list[RobotTimeEntityDescription[LitterRobot5]] = [
    RobotTimeEntityDescription[LitterRobot5](
        key="sleep_mode_start_time",
        translation_key="sleep_mode_start_time",
        entity_category=EntityCategory.CONFIG,
        value_fn=_lr5_sleep_start,
        set_fn=lambda robot, value: robot.set_sleep_mode(
            robot.sleep_mode_enabled,
            sleep_time=value,
        ),
    ),
    RobotTimeEntityDescription[LitterRobot5](
        key="sleep_mode_end_time",
        translation_key="sleep_mode_end_time",
        entity_category=EntityCategory.CONFIG,
        value_fn=_lr5_sleep_end,
        set_fn=lambda robot, value: robot.set_sleep_mode(
            robot.sleep_mode_enabled,
            wake_time=value.hour * 60 + value.minute,
        ),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LitterRobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Litter-Robot cleaner using config entry."""
    coordinator = entry.runtime_data
    entities: list[LitterRobotTimeEntity] = [
        LitterRobotTimeEntity(
            robot=robot,
            coordinator=coordinator,
            description=LITTER_ROBOT_3_SLEEP_START,
        )
        for robot in coordinator.litter_robots()
        if isinstance(robot, LitterRobot3)
    ]
    entities.extend(
        LitterRobotTimeEntity(
            robot=robot,
            coordinator=coordinator,
            description=description,
        )
        for robot in coordinator.litter_robots()
        if isinstance(robot, LitterRobot5)
        for description in LITTER_ROBOT_5_TIME_ENTITIES
    )
    async_add_entities(entities)


class LitterRobotTimeEntity(LitterRobotEntity[_WhiskerEntityT], TimeEntity):
    """Litter-Robot time entity."""

    entity_description: RobotTimeEntityDescription[_WhiskerEntityT]

    @property
    def native_value(self) -> time | None:
        """Return the value reported by the time."""
        return self.entity_description.value_fn(self.robot)

    @whisker_command
    async def async_set_value(self, value: time) -> None:
        """Update the current value."""
        await self.entity_description.set_fn(self.robot, value)
