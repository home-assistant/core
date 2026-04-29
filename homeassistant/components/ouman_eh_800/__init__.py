"""The Ouman EH-800 integration."""

from __future__ import annotations

from datetime import timedelta

from ouman_eh_800_api import OumanEh800Client

from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_SCAN_INTERVAL_SECONDS
from .coordinator import OumanEh800ConfigEntry, OumanEh800Coordinator

_PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: OumanEh800ConfigEntry) -> bool:
    """Set up Ouman EH-800 from a config entry."""
    client = OumanEh800Client(
        session=async_get_clientsession(hass),
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        address=entry.data[CONF_URL],
    )

    coordinator = OumanEh800Coordinator(
        hass, entry, client, timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS)
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OumanEh800ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
