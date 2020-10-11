"""The TP-Link EAP integration."""
import asyncio

from pytleap import Eap

from homeassistant.components.device_tracker.const import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS = [DEVICE_TRACKER_DOMAIN]


async def async_setup(hass: HomeAssistant, config):
    """Set up the TP-Link EAP component.

    Configuration through YAML is not supported at this time.
    """
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up TP-Link EAP from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    url = entry.data[CONF_URL]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    hass.data[DOMAIN][entry.entry_id] = Eap(url, username, password)

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
