"""The Vegetronix VegeHub integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from . import http_api
from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

# If your integration is only set up through the UI (config flow)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the VegeHub integration."""
    return True  # For now, we are not using YAML config.


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up VegeHub from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Register the device in the device registrys
    device_registry = dr.async_get(hass)

    if device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)}):
        _LOGGER.error("Device %s is already registered!", entry.entry_id)
        return False

    # Register the device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, str(entry.data.get("mac_address")))},
        identifiers={(DOMAIN, str(entry.data.get("mac_address")))},
        manufacturer="Vegetronix",
        model="VegeHub",
        name=entry.data.get("hostname"),
        sw_version=entry.data.get("sw_ver"),
        configuration_url=entry.data.get("config_url"),
    )

    # Now add in all the entities for this device.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    hass.loop.create_task(http_api.async_setup(hass))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a VegeHub config entry."""

    # Unload platforms (like sensor)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # If successful, clean up resources
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
