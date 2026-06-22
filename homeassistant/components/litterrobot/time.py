"""Support for Litter-Robot time."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime, time
from functools import partial
from typing import Any, Generic, override

from pylitterbot import LitterRobot3, LitterRobot5, Robot
from pylitterbot.sleep_schedule import DayOfWeek, SleepScheduleDay

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import LitterRobotConfigEntry
from .entity import (
    LitterRobotEntity,
    _WhiskerEntityT,
    raise_update_failed,
    whisker_command,
)

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class RobotTimeEntityDescription(TimeEntityDescription, Generic[_WhiskerEntityT]):  # noqa: UP046
    """A class that describes robot time entities."""

    value_fn: Callable[[_WhiskerEntityT], time | None]
    set_fn: Callable[[_WhiskerEntityT, time], Coroutine[Any, Any, bool]]


def _as_local_time(start: datetime | None) -> time | None:
    """Return a datetime as local time."""
    return dt_util.as_local(start).time() if start else None


def _lr5_schedule_day(robot: LitterRobot5, day: DayOfWeek) -> SleepScheduleDay | None:
    """Return the robot's sleep schedule entry for a day."""
    if (schedule := robot.sleep_schedule) is None:
        return None
    return schedule.get_day(day)


def _lr5_schedule_time(
    robot: LitterRobot5, *, day: DayOfWeek, wake: bool
) -> time | None:
    """Return a day's configured sleep start or wake time.

    The schedule stores wall-clock times in the robot's own timezone, so the
    value is reported as-is (unlike Litter-Robot 3, which stores a UTC
    datetime that must be converted).
    """
    if (entry := _lr5_schedule_day(robot, day)) is None:
        return None
    return entry.wake_time if wake else entry.sleep_time


async def _lr5_set_schedule_time(
    robot: LitterRobot5, value: time, *, day: DayOfWeek, wake: bool
) -> bool:
    """Set a day's sleep start or wake time, preserving its enabled state.

    The schedule is minute-granular; seconds are dropped.
    """
    entry = _lr5_schedule_day(robot, day)
    enabled = entry.is_enabled if entry else False
    minutes = value.hour * 60 + value.minute
    if wake:
        return await robot.set_sleep_mode(enabled, wake_time=minutes, day_of_week=day)
    return await robot.set_sleep_mode(enabled, minutes, day_of_week=day)


LITTER_ROBOT_5_SLEEP_TIMES: tuple[RobotTimeEntityDescription[LitterRobot5], ...] = (
    tuple(
        RobotTimeEntityDescription[LitterRobot5](
            key=f"sleep_mode_{kind}_time_{day.name.lower()}",
            translation_key=f"sleep_mode_{kind}_time_{day.name.lower()}",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
            value_fn=partial(_lr5_schedule_time, day=day, wake=wake),
            set_fn=partial(_lr5_set_schedule_time, day=day, wake=wake),
        )
        for day in DayOfWeek
        for kind, wake in (("start", False), ("end", True))
    )
)

ROBOT_TIME_MAP: dict[type[Robot], tuple[RobotTimeEntityDescription[Any], ...]] = {
    LitterRobot3: (
        RobotTimeEntityDescription[LitterRobot3](
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
        ),
    ),
    LitterRobot5: LITTER_ROBOT_5_SLEEP_TIMES,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LitterRobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Litter-Robot cleaner using config entry."""
    coordinator = entry.runtime_data
    known_robots: set[str] = set()

    def _check_robots() -> None:
        all_robots = list(coordinator.litter_robots())
        current_robots = {robot.serial for robot in all_robots}
        new_robots = current_robots - known_robots
        if new_robots:
            known_robots.update(new_robots)
            async_add_entities(
                LitterRobotTimeEntity(
                    robot=robot, coordinator=coordinator, description=description
                )
                for robot in all_robots
                if robot.serial in new_robots
                for robot_type, descriptions in ROBOT_TIME_MAP.items()
                if isinstance(robot, robot_type)
                for description in descriptions
            )

    _check_robots()
    entry.async_on_unload(coordinator.async_add_listener(_check_robots))


class LitterRobotTimeEntity(LitterRobotEntity[_WhiskerEntityT], TimeEntity):
    """Litter-Robot time entity."""

    entity_description: RobotTimeEntityDescription[_WhiskerEntityT]

    @property
    @override
    def native_value(self) -> time | None:
        """Return the value reported by the time."""
        return self.entity_description.value_fn(self.robot)

    @whisker_command
    @override
    async def async_set_value(self, value: time) -> None:
        """Update the current value."""
        if not await self.entity_description.set_fn(self.robot, value):
            raise_update_failed(self.entity_id)
