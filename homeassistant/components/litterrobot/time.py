"""Support for Litter-Robot time."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Generic

from pylitterbot import LitterRobot3

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import LitterRobotConfigEntry
from .entity import LitterRobotEntity, _WhiskerEntityT


@dataclass(frozen=True, kw_only=True)
class RobotTimeEntityDescription(TimeEntityDescription, Generic[_WhiskerEntityT]):
    """A class that describes robot time entities."""

    value_fn: Callable[[_WhiskerEntityT], time | None]
    set_fn: Callable[[_WhiskerEntityT, time], Coroutine[Any, Any, bool]]


def _as_local_time(start: datetime | None) -> time | None:
    """Return a datetime as local time."""
    return dt_util.as_local(start).time() if start else None


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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LitterRobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Litter-Robot cleaner using config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        LitterRobotTimeEntity(
            robot=robot,
            coordinator=coordinator,
            description=LITTER_ROBOT_3_SLEEP_START,
        )
        for robot in coordinator.litter_robots()
        if isinstance(robot, LitterRobot3)
    )


class LitterRobotTimeEntity(LitterRobotEntity[_WhiskerEntityT], TimeEntity):
    """Litter-Robot time entity."""

    entity_description: RobotTimeEntityDescription[_WhiskerEntityT]

    @property
    def native_value(self) -> time | None:
        """Return the value reported by the time."""
        return self.entity_description.value_fn(self.robot)

    async def async_set_value(self, value: time) -> None:
        """Update the current value."""
        await self.entity_description.set_fn(self.robot, value)
