"""The Suez Water integration."""

from __future__ import annotations

import asyncio

from pysuez import SuezClient
from pysuez.client import PySuezError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import CONF_COUNTER_ID, DOMAIN
from .coordinator import SuezWaterCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


def _get_client(entry: ConfigEntry) -> SuezClient:
    try:
        client = SuezClient(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data[CONF_COUNTER_ID],
            provider=None,
        )
        if not client.check_credentials():
            raise ConfigEntryError
    except PySuezError as ex:
        raise ConfigEntryNotReady from ex
    return client


async def _get_coordinator(
    hass: HomeAssistant, entry: ConfigEntry
) -> SuezWaterCoordinator:
    loop = asyncio.get_running_loop()
    client = await loop.run_in_executor(None, _get_client, entry)
    coordinator = SuezWaterCoordinator(hass, client, entry.data[CONF_COUNTER_ID])
    await coordinator.async_config_entry_first_refresh()
    return coordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Suez Water from a config entry."""

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = await _get_coordinator(
        hass, entry
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
