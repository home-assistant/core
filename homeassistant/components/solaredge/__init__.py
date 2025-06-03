"""The SolarEdge integration."""

from __future__ import annotations

import socket

from aiohttp import ClientError
from aiosolaredge import SolarEdge

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SITE_ID, LOGGER
from .types import SolarEdgeConfigEntry, SolarEdgeData

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SolarEdgeConfigEntry) -> bool:
    """Set up SolarEdge from a config entry."""
    session = async_get_clientsession(hass)
    api = SolarEdge(entry.data[CONF_API_KEY], session)

    try:
        response = await api.get_details(entry.data[CONF_SITE_ID])
    except (TimeoutError, ClientError, socket.gaierror) as ex:
        LOGGER.error("Could not retrieve details from SolarEdge API")
        raise ConfigEntryNotReady from ex

    if "details" not in response:
        LOGGER.error("Missing details data in SolarEdge response")
        raise ConfigEntryNotReady

    if response["details"].get("status", "").lower() != "active":
        LOGGER.error("SolarEdge site is not active")
        return False

    entry.runtime_data = SolarEdgeData(api_client=api)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SolarEdgeConfigEntry) -> bool:
    """Unload SolarEdge config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
