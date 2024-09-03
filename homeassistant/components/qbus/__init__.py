"""The Qbus integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import QbusDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Qbus from a config entry."""

    if not await mqtt.async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration not available")
        return False

    if TYPE_CHECKING:
        assert config_entry.unique_id is not None

    hass.data.setdefault(DOMAIN, {})
    hub = hass.data[DOMAIN].get(config_entry.entry_id)

    if not hub:
        hub = QbusDataUpdateCoordinator(hass, config_entry)
        # hub = QbusDataUpdateCoordinator(hass, config_entry.entry_id)
        hass.data[DOMAIN][config_entry.entry_id] = hub

    await hub.async_setup_entry()

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        hass.data[DOMAIN].pop(config_entry.entry_id)
    return unload_ok
