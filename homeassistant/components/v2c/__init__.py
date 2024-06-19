"""The V2C integration."""

from __future__ import annotations

from pytrydan import Trydan

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .coordinator import V2CUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


type V2CConfigEntry = ConfigEntry[V2CUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: V2CConfigEntry) -> bool:
    """Set up V2C from a config entry."""

    host = entry.data[CONF_HOST]
    trydan = Trydan(host, get_async_client(hass, verify_ssl=False))
    coordinator = V2CUpdateCoordinator(hass, trydan, host)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    if coordinator.data.ID and entry.unique_id != coordinator.data.ID:
        hass.config_entries.async_update_entry(entry, unique_id=coordinator.data.ID)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
