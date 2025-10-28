"""Integration for eGauge energy monitors."""

from __future__ import annotations

from egauge_async.json.client import EgaugeJsonClient

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .coordinator import EgaugeConfigEntry, EgaugeDataCoordinator
from .util import _build_client_url

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: EgaugeConfigEntry) -> bool:
    """Set up eGauge from a config entry."""
    # Create API client

    client = EgaugeJsonClient(
        base_url=_build_client_url(entry.data[CONF_HOST], entry.data[CONF_SSL]),
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        client=get_async_client(hass, verify_ssl=entry.data[CONF_VERIFY_SSL]),
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
