"""Support for Litter-Robot switches."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic

from pylitterbot import FeederRobot, LitterRobot

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LitterRobotConfigEntry
from .entity import LitterRobotEntity, _WhiskerEntityT


@dataclass(frozen=True, kw_only=True)
class RobotSwitchEntityDescription(SwitchEntityDescription, Generic[_WhiskerEntityT]):
    """A class that describes robot switch entities."""

    entity_category: EntityCategory = EntityCategory.CONFIG
    set_fn: Callable[[_WhiskerEntityT, bool], Coroutine[Any, Any, bool]]
    value_fn: Callable[[_WhiskerEntityT], bool]


ROBOT_SWITCHES = [
    RobotSwitchEntityDescription[LitterRobot | FeederRobot](
        key="night_light_mode_enabled",
        translation_key="night_light_mode",
        set_fn=lambda robot, value: robot.set_night_light(value),
        value_fn=lambda robot: robot.night_light_mode_enabled,
    ),
    RobotSwitchEntityDescription[LitterRobot | FeederRobot](
        key="panel_lock_enabled",
        translation_key="panel_lockout",
        set_fn=lambda robot, value: robot.set_panel_lockout(value),
        value_fn=lambda robot: robot.panel_lock_enabled,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LitterRobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Litter-Robot switches using config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        RobotSwitchEntity(robot=robot, coordinator=coordinator, description=description)
        for description in ROBOT_SWITCHES
        for robot in coordinator.account.robots
        if isinstance(robot, (LitterRobot, FeederRobot))
    )


class RobotSwitchEntity(LitterRobotEntity[_WhiskerEntityT], SwitchEntity):
    """Litter-Robot switch entity."""

    entity_description: RobotSwitchEntityDescription[_WhiskerEntityT]

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self.entity_description.value_fn(self.robot)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.set_fn(self.robot, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.set_fn(self.robot, False)
