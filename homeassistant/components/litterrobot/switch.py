"""Support for Litter-Robot switches."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LitterRobotControlEntity
from .hub import LitterRobotHub


class LitterRobotNightLightModeSwitch(LitterRobotControlEntity, SwitchEntity):
    """Litter-Robot Night Light Mode Switch."""

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.robot.night_light_mode_enabled

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:lightbulb-on" if self.is_on else "mdi:lightbulb-off"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.perform_action_and_refresh(self.robot.set_night_light, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.perform_action_and_refresh(self.robot.set_night_light, False)


class LitterRobotPanelLockoutSwitch(LitterRobotControlEntity, SwitchEntity):
    """Litter-Robot Panel Lockout Switch."""

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.robot.panel_lock_enabled

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:lock" if self.is_on else "mdi:lock-open"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.perform_action_and_refresh(self.robot.set_panel_lockout, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.perform_action_and_refresh(self.robot.set_panel_lockout, False)


ROBOT_SWITCHES: list[tuple[type[LitterRobotControlEntity], str]] = [
    (LitterRobotNightLightModeSwitch, "Night Light Mode"),
    (LitterRobotPanelLockoutSwitch, "Panel Lockout"),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Litter-Robot switches using config entry."""
    hub: LitterRobotHub = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for robot in hub.account.robots:
        for switch_class, switch_type in ROBOT_SWITCHES:
            entities.append(switch_class(robot=robot, entity_type=switch_type, hub=hub))

    async_add_entities(entities, True)
