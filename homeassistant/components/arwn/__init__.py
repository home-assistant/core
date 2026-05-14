"""The arwn component."""

from __future__ import annotations

import logging

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .sensor import ArwnSensor

_LOGGER = logging.getLogger(__name__)

type ArwnConfigEntry = ConfigEntry[dict[str, ArwnSensor]]

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ArwnConfigEntry) -> bool:
    """Set up ARWN from a config entry."""
    if not await mqtt.async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration is not available")
        return False

    entry.runtime_data = {}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ArwnConfigEntry) -> bool:
    """Unload ARWN config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
