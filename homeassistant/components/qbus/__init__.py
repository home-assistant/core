"""The Qbus integration."""

from __future__ import annotations

import logging

from homeassistant.components.mqtt import async_wait_for_mqtt_client
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import Event, HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import QbusDataCoordinator
from .qbus import QbusConfigContainer

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Qbus from a config entry."""
    _LOGGER.debug("Loading entry %s", entry.entry_id)

    if not await async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration not available")
        return False

    hass.data.setdefault(DOMAIN, {})
    hub = hass.data[DOMAIN].get(entry.entry_id)

    if not hub:
        hub = QbusDataCoordinator(hass, entry)
        hass.data[DOMAIN][entry.entry_id] = hub

    await hub.async_setup_entry()

    async def _homeassistant_started(event: Event) -> None:
        _LOGGER.debug("Home Assistant started, requesting config")
        await QbusConfigContainer.async_get_or_request_config(hass)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _homeassistant_started)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading entry %s", entry.entry_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hub: QbusDataCoordinator = hass.data[DOMAIN][entry.entry_id]
        hub.shutdown()

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry."""
    _LOGGER.debug("Removing entry %s", entry.entry_id)

    hub: QbusDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    hub.remove()
    hass.data[DOMAIN].pop(entry.entry_id)
