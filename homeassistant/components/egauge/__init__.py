"""Integration for eGauge energy monitors."""

from __future__ import annotations

from egauge_async.json.client import EgaugeJsonClient

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import EgaugeDataCoordinator
from .models import EgaugeConfigEntry

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: EgaugeConfigEntry) -> bool:
    """Set up eGauge from a config entry."""
    # Create API client
    client = EgaugeJsonClient(
        base_url=entry.data[CONF_HOST],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        client=async_get_clientsession(hass),
    )

    # Create coordinator (it fetches its own data)
    coordinator = EgaugeDataCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator in runtime_data
    entry.runtime_data = coordinator

    # Setup sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EgaugeConfigEntry) -> bool:
    """Unload eGauge config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
