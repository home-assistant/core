"""Switch platform for MicroBot."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform

from .const import DOMAIN
from .entity import MicroBotEntity

if TYPE_CHECKING:
    from . import MicroBotDataUpdateCoordinator

CALIBRATE = "calibrate"
CALIBRATE_SCHEMA = {
    vol.Required("depth"): cv.positive_int,
    vol.Required("duration"): cv.positive_int,
    vol.Required("mode"): vol.In(["normal", "invert", "toggle"]),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
) -> None:
    """Set up MicroBot based on a config entry."""
    coordinator: MicroBotDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MicroBotBinarySwitch(coordinator, entry)])
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        CALIBRATE,
        CALIBRATE_SCHEMA,
        "async_calibrate",
    )


class MicroBotBinarySwitch(MicroBotEntity, SwitchEntity):
    """MicroBot switch class."""

    _attr_has_entity_name = True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.coordinator.api.push_on()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.coordinator.api.push_off()
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.coordinator.api.is_on

    async def async_calibrate(
        self,
        depth: int,
        duration: int,
        mode: str,
    ) -> None:
        """Send calibration commands to the switch."""
        await self.coordinator.api.calibrate(depth, duration, mode)
