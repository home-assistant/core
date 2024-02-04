"""Arctic Spa Light."""
from __future__ import annotations

import logging
from typing import Any

from pyarcticspas import LightState
from pyarcticspas.error import SpaHTTPException

from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import ArcticSpaEntity, async_refresh_after

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Arctic Spa Light from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([SpaLight(coordinator)])


class SpaLight(ArcticSpaEntity, LightEntity):
    """Represents the Arctic Spa light."""

    _attr_translation_key = "light"

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self.coordinator.data.lights == LightState["ON"]

    @async_refresh_after
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        try:
            await self.coordinator.device.async_set_lights(LightState["ON"])
        except SpaHTTPException as e:
            _LOGGER.error("Error turning ArcticSpa light on: %d %s", e.code, e.msg)

    @async_refresh_after
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        try:
            await self.coordinator.device.async_set_lights(LightState["OFF"])
        except SpaHTTPException as e:
            _LOGGER.error("Error turning ArcticSpa light off: %d %s", e.code, e.msg)
