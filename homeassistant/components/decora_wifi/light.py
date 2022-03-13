"""Interfaces with the myLeviton API for Decora Smart WiFi products."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import BaseDecoraWifiEntity, EntityTypes, _setup_platform

_LOGGER = logging.getLogger(__name__)


class DecoraWifiLight(BaseDecoraWifiEntity, LightEntity):
    """Encapsulates functionality specific to Decora WiFi fan controllers."""

    @property
    def supported_features(self) -> int:
        """Return the switch's supported features."""

        if self._switch.canSetLevel:
            return SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION
        return 0

    @property
    def brightness(self) -> int:
        """Return the switch's current brightness."""

        return int(self._switch.brightness * 255 / 100)

    def turn_on(self, **kwargs: dict[str, Any]) -> None:
        """Turn the light on and adjust brightness."""

        attribs: dict[str, Any] = {"power": "ON"}

        if ATTR_BRIGHTNESS in kwargs:
            min_level = self._switch.data.get("minLevel", 0)
            max_level = self._switch.data.get("maxLevel", 100)
            brightness = int(kwargs[ATTR_BRIGHTNESS] * max_level / 255)
            brightness = max(brightness, min_level)
            attribs["brightness"] = brightness

        if ATTR_TRANSITION in kwargs:
            transition = kwargs[ATTR_TRANSITION]
            attribs["fadeOnTime"] = attribs["fadeOffTime"] = transition

        try:
            self._switch.update_attributes(attribs)
        except ValueError:
            _LOGGER.error("Failed to turn on myLeviton switch")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Decora lights."""

    await hass.async_add_executor_job(
        _setup_platform,
        EntityTypes.LIGHT,
        DecoraWifiLight,
        hass,
        config_entry,
        async_add_entities,
    )
