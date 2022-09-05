"""Support for Litter-Robot switches."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic, Union

from pylitterbot import FeederRobot, LitterRobot

from homeassistant.components.switch import (
    DOMAIN as PLATFORM,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LitterRobotConfigEntity, _RobotT, async_update_unique_id
from .hub import LitterRobotHub


@dataclass
class RequiredKeysMixin(Generic[_RobotT]):
    """A class that describes robot switch entity required keys."""

    icons: tuple[str, str]
    set_fn: Callable[[_RobotT], Callable[[bool], Coroutine[Any, Any, bool]]]


@dataclass
class RobotSwitchEntityDescription(SwitchEntityDescription, RequiredKeysMixin[_RobotT]):
    """A class that describes robot switch entities."""


ROBOT_SWITCHES = [
    RobotSwitchEntityDescription[Union[LitterRobot, FeederRobot]](
        key="night_light_mode_enabled",
        name="Night Light Mode",
        icons=("mdi:lightbulb-on", "mdi:lightbulb-off"),
        set_fn=lambda robot: robot.set_night_light,
    ),
    RobotSwitchEntityDescription[Union[LitterRobot, FeederRobot]](
        key="panel_lock_enabled",
        name="Panel Lockout",
        icons=("mdi:lock", "mdi:lock-open"),
        set_fn=lambda robot: robot.set_panel_lockout,
    ),
]


class RobotSwitchEntity(LitterRobotConfigEntity[_RobotT], SwitchEntity):
    """Litter-Robot switch entity."""

    entity_description: RobotSwitchEntityDescription[_RobotT]

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        if self._refresh_callback is not None:
            return self._assumed_state
        return bool(getattr(self.robot, self.entity_description.key))

    @property
    def icon(self) -> str:
        """Return the icon."""
        icon_on, icon_off = self.entity_description.icons
        return icon_on if self.is_on else icon_off

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        set_fn = self.entity_description.set_fn
        await self.perform_action_and_assume_state(set_fn(self.robot), True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        set_fn = self.entity_description.set_fn
        await self.perform_action_and_assume_state(set_fn(self.robot), False)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Litter-Robot switches using config entry."""
    hub: LitterRobotHub = hass.data[DOMAIN][entry.entry_id]
    entities = [
        RobotSwitchEntity(robot=robot, hub=hub, description=description)
        for description in ROBOT_SWITCHES
        for robot in hub.account.robots
        if isinstance(robot, (LitterRobot, FeederRobot))
    ]
    async_update_unique_id(hass, PLATFORM, entities)
    async_add_entities(entities)
