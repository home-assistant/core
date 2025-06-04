"""The Altruist Sensor integration."""

from __future__ import annotations

import logging

from altruistclient import AltruistClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

type AltruistConfigEntry = ConfigEntry[AltruistClient]


async def async_setup_entry(hass: HomeAssistant, entry: AltruistConfigEntry) -> bool:
    """Set up Hello World from a config entry."""
    session = async_get_clientsession(hass)
    try:
        client = await AltruistClient.from_ip_address(session, entry.data["ip_address"])
        await client.fetch_data()
    except Exception as e:
        _LOGGER.error("Error in Altruist setup: %s", e)
        raise ConfigEntryNotReady from e
    entry.runtime_data = client
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # This is called when an entry/configured device is to be removed. The class
    # needs to unload itself, and remove callbacks. See the classes for further
    # details
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
