"""The SolarEdge integration."""

from __future__ import annotations

import socket

from aiohttp import ClientError
from aiosolaredge import SolarEdge

from homeassistant.const import CONF_API_KEY, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SITE_ID, DATA_API_CLIENT, DATA_MODULES_COORDINATOR, LOGGER
from .coordinator import SolarEdgeModulesCoordinator
from .types import SolarEdgeConfigEntry, SolarEdgeData

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SolarEdgeConfigEntry) -> bool:
    """Set up SolarEdge from a config entry."""
    entry.runtime_data = SolarEdgeData()
    site_id = entry.data[CONF_SITE_ID]

    # Setup for API key (sensors)
    if CONF_API_KEY in entry.data:
        session = async_get_clientsession(hass)
        api = SolarEdge(entry.data[CONF_API_KEY], session)

        try:
            response = await api.get_details(site_id)
        except (TimeoutError, ClientError, socket.gaierror) as ex:
            LOGGER.error("Could not retrieve details from SolarEdge API")
            raise ConfigEntryNotReady from ex

        if "details" not in response:
            LOGGER.error("Missing details data in SolarEdge response")
            raise ConfigEntryNotReady

        if response["details"].get("status", "").lower() != "active":
            LOGGER.error("SolarEdge site is not active")
            return False

        entry.runtime_data[DATA_API_CLIENT] = api
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Setup for username/password (modules statistics)
    if CONF_USERNAME in entry.data:
        coordinator = SolarEdgeModulesCoordinator(hass, entry)
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data[DATA_MODULES_COORDINATOR] = coordinator

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SolarEdgeConfigEntry) -> bool:
    """Unload SolarEdge config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
