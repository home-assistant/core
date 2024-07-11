"""Switch platform for MicroBot."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN
from .coordinator import MicroBotDataUpdateCoordinator
from .entity import MicroBotEntity

CALIBRATE = "calibrate"
CALIBRATE_SCHEMA: VolDictType = {
    vol.Required("depth"): cv.positive_int,
    vol.Required("duration"): cv.positive_int,
    vol.Required("mode"): vol.In(["normal", "invert", "toggle"]),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up MicroBot based on a config entry."""
    coordinator: MicroBotDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MicroBotBinarySwitch(coordinator, entry)])
    platform = async_get_current_platform()
    platform.async_register_entity_service(
        CALIBRATE,
        CALIBRATE_SCHEMA,
        "async_calibrate",
    )


class MicroBotBinarySwitch(MicroBotEntity, SwitchEntity):
    """MicroBot switch class."""

    _attr_translation_key = "push"

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
