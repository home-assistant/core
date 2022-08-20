"""The Detailed MHTZN integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .Gateway import Gateway
from .const import PLATFORMS, MQTT_CLIENT_INSTANCE, CONF_LIGHT_DEVICE_TYPE, DOMAIN, FLAG_IS_INITIALIZED, \
    CACHE_ENTITY_STATE_UPDATE_KEY_DICT

_LOGGER = logging.getLogger(__name__)


async def _async_config_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """This method is triggered when the entry configuration changes, and the gateway link information is updated"""

    """Get gateway instance"""
    hub = hass.data[DOMAIN][entry.unique_id]
    """reconnect gateway"""
    await hub.reconnect(entry)
    """Initialize gateway information and synchronize child device list to HA"""
    await hub.init()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""

    """Create a gateway instance"""
    hub = Gateway(hass, entry)

    hass.data.setdefault(DOMAIN, {})[entry.unique_id] = hub

    """Set a flag to record whether the current integration has been initialized"""
    if FLAG_IS_INITIALIZED not in hass.data:
        hass.data[FLAG_IS_INITIALIZED] = False

    """Set a dictionary to record whether the sub-device state change event has been created, 
    to avoid the same device from repeatedly creating state change events"""
    if CACHE_ENTITY_STATE_UPDATE_KEY_DICT not in hass.data:
        hass.data[CACHE_ENTITY_STATE_UPDATE_KEY_DICT] = {}

    """Determine whether the current integration has been initialized to avoid repeated installation of platform list"""
    if not hass.data[FLAG_IS_INITIALIZED]:
        hass.data[FLAG_IS_INITIALIZED] = True
        hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    """Connection gateway"""
    await hub.connect()

    """Initialize gateway information and synchronize child device list to HA"""
    await hub.init()

    """Add an entry configuration change event listener to trigger the specified method 
    when the configuration changes"""
    entry.add_update_listener(_async_config_entry_updated)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """This method is triggered when the entry is unload"""

    hub = hass.data[DOMAIN].pop(entry.unique_id)
    """Perform a gateway disconnect operation"""
    await hub.disconnect()

    return True
