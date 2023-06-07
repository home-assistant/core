"""Support for Litter-Robot time."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import time
from typing import Any, Generic

from pylitterbot import LitterRobot3

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .entity import LitterRobotEntity, _RobotT
from .hub import LitterRobotHub


@dataclass
class RequiredKeysMixin(Generic[_RobotT]):
    """A class that describes robot time entity required keys."""

    value_fn: Callable[[_RobotT], time | None]
    set_fn: Callable[[_RobotT, time], Coroutine[Any, Any, bool]]


@dataclass
class RobotTimeEntityDescription(TimeEntityDescription, RequiredKeysMixin[_RobotT]):
    """A class that describes robot time entities."""


LITTER_ROBOT_3_SLEEP_START = RobotTimeEntityDescription[LitterRobot3](
    key="sleep_mode_start_time",
    name="Sleep mode start time",
    entity_category=EntityCategory.CONFIG,
    value_fn=lambda robot: dt_util.as_local(start).time()
    if (start := robot.sleep_mode_start_time)
    else None,
    set_fn=lambda robot, value: robot.set_sleep_mode(
        robot.sleep_mode_enabled, value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Litter-Robot cleaner using config entry."""
    hub: LitterRobotHub = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            LitterRobotTimeEntity(
                robot=robot, hub=hub, description=LITTER_ROBOT_3_SLEEP_START
            )
            for robot in hub.litter_robots()
            if isinstance(robot, LitterRobot3)
        ]
    )


class LitterRobotTimeEntity(LitterRobotEntity[_RobotT], TimeEntity):
    """Litter-Robot time entity."""

    entity_description: RobotTimeEntityDescription[_RobotT]

    @property
    def native_value(self) -> time | None:
        """Return the value reported by the time."""
        return self.entity_description.value_fn(self.robot)

    async def async_set_value(self, value: time) -> None:
        """Update the current value."""
        await self.entity_description.set_fn(self.robot, value)
