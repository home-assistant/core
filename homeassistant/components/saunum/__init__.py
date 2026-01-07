"""The Saunum Leil Sauna Control Unit integration."""

from __future__ import annotations

from pysaunum import SaunumClient, SaunumConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import LeilSaunaCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.LIGHT,
    Platform.SENSOR,
]

type LeilSaunaConfigEntry = ConfigEntry[LeilSaunaCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: LeilSaunaConfigEntry) -> bool:
    """Set up Saunum Leil Sauna from a config entry."""
    host = entry.data[CONF_HOST]

    client = SaunumClient(host=host)

    # Test connection
    try:
        await client.connect()
    except SaunumConnectionError as exc:
        raise ConfigEntryNotReady(f"Error connecting to {host}: {exc}") from exc

    coordinator = LeilSaunaCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LeilSaunaConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = entry.runtime_data
        coordinator.client.close()

    return unload_ok
