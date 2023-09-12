"""Support for Litter-Robot switches."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic

from pylitterbot import FeederRobot, LitterRobot

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LitterRobotEntity, _RobotT
from .hub import LitterRobotHub


@dataclass
class RequiredKeysMixin(Generic[_RobotT]):
    """A class that describes robot switch entity required keys."""

    icons: tuple[str, str]
    set_fn: Callable[[_RobotT, bool], Coroutine[Any, Any, bool]]


@dataclass
class RobotSwitchEntityDescription(SwitchEntityDescription, RequiredKeysMixin[_RobotT]):
    """A class that describes robot switch entities."""

    entity_category: EntityCategory = EntityCategory.CONFIG


ROBOT_SWITCHES = [
    RobotSwitchEntityDescription[LitterRobot | FeederRobot](
        key="night_light_mode_enabled",
        translation_key="night_light_mode",
        icons=("mdi:lightbulb-on", "mdi:lightbulb-off"),
        set_fn=lambda robot, value: robot.set_night_light(value),
    ),
    RobotSwitchEntityDescription[LitterRobot | FeederRobot](
        key="panel_lock_enabled",
        translation_key="panel_lockout",
        icons=("mdi:lock", "mdi:lock-open"),
        set_fn=lambda robot, value: robot.set_panel_lockout(value),
    ),
]


class RobotSwitchEntity(LitterRobotEntity[_RobotT], SwitchEntity):
    """Litter-Robot switch entity."""

    entity_description: RobotSwitchEntityDescription[_RobotT]

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return bool(getattr(self.robot, self.entity_description.key))

    @property
    def icon(self) -> str:
        """Return the icon."""
        icon_on, icon_off = self.entity_description.icons
        return icon_on if self.is_on else icon_off

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.set_fn(self.robot, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.set_fn(self.robot, False)


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
    async_add_entities(entities)
