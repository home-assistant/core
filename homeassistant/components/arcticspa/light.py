"""Arctic Spa Light."""
from __future__ import annotations

import logging
from typing import Any

from pyarcticspas import LightState

from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import CoordinatedEntity, async_refresh_after
from .hottub import Device

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Arctic Spa Light from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([SpaLight(coordinator.device, coordinator)])


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload Arctic Spa."""
    _ = hass.data[DOMAIN].pop(entry.data[CONF_API_KEY])


class SpaLight(CoordinatedEntity, LightEntity):
    """Represents the Arctic Spa light."""

    _attr_name = "Light"

    device: Device

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self.status.lights == LightState["ON"]

    @async_refresh_after
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        await self.device.api.async_set_lights(LightState["ON"])
        self.status.lights = LightState[
            "ON"
        ]  # Temporary solution because of API filtering.

    @async_refresh_after
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        await self.device.api.async_set_lights(LightState["OFF"])
        self.status.lights = LightState[
            "ON"
        ]  # Temporary solution because of API filtering.
