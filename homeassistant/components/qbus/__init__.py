"""The Qbus integration."""

from __future__ import annotations

import logging

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .qbus import QbusHub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Qbus from a config entry."""
    _LOGGER.debug("Loading %s for entry %s", DOMAIN, entry.entry_id)

    if not await mqtt.async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration not available")
        return False

    hass.data.setdefault(DOMAIN, {})
    hub = hass.data[DOMAIN].get(entry.entry_id)

    if not hub:
        hub = QbusHub(hass, entry)
        hass.data[DOMAIN][entry.entry_id] = hub

    await hub.async_setup_entry()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading %s for entry %s", DOMAIN, entry.entry_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hub: QbusHub = hass.data[DOMAIN][entry.entry_id]
        hub.shutdown()

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry."""
    _LOGGER.debug("Removing %s for entry %s", DOMAIN, entry.entry_id)

    hub: QbusHub = hass.data[DOMAIN][entry.entry_id]
    hub.remove()
    hass.data[DOMAIN].pop(entry.entry_id)
