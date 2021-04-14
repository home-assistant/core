"""Kuler Sky lights integration."""
import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_ADDRESSES, DATA_DISCOVERY_SUBSCRIPTION, DOMAIN

PLATFORMS = ["light"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Kuler Sky component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Kuler Sky from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    if DATA_ADDRESSES not in hass.data[DOMAIN]:
        hass.data[DOMAIN][DATA_ADDRESSES] = set()

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    # Stop discovery
    unregister_discovery = hass.data[DOMAIN].pop(DATA_DISCOVERY_SUBSCRIPTION, None)
    if unregister_discovery:
        unregister_discovery()

    hass.data.pop(DOMAIN, None)

    return all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
