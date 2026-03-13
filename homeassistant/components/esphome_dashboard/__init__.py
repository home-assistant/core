"""Support for ESPHome Dashboard."""

from __future__ import annotations

import logging

import aiohttp
from esphome_dashboard_api import ESPHomeDashboardAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN as DOMAIN
from .coordinator import ESPHomeDashboardCoordinator
from .models import ESPHomeDashboardRuntimeData

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.UPDATE]

type ESPHomeDashboardConfigEntry = ConfigEntry[ESPHomeDashboardRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant, entry: ESPHomeDashboardConfigEntry
) -> bool:
    """Set up ESPHome Dashboard from a config entry."""
    url = entry.data[CONF_URL]
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)

    # Create session with authentication if credentials are provided
    auth = aiohttp.BasicAuth(username, password) if username and password else None
    session = aiohttp_client.async_create_clientsession(
        hass, auth=auth, raise_for_status=True
    )
    api = ESPHomeDashboardAPI(url, session)

    coordinator = ESPHomeDashboardCoordinator(hass, api, entry)

    await coordinator.async_config_entry_first_refresh()

    # Store both coordinator and session for proper cleanup
    entry.runtime_data = ESPHomeDashboardRuntimeData(
        coordinator=coordinator,
        session=session,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ESPHomeDashboardConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Close the aiohttp session to prevent resource leaks
        await entry.runtime_data.session.close()

    return unload_ok
