"""The Meteo.lt integration."""

from __future__ import annotations

from meteo_lt import MeteoLtAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_PLACE_CODE, PLATFORMS
from .coordinator import MeteoLtUpdateCoordinator

type MeteoLtConfigEntry = ConfigEntry[MeteoLtUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: MeteoLtConfigEntry) -> bool:
    """Set up Meteo.lt from a config entry."""
    place_code = entry.data[CONF_PLACE_CODE]

    client = MeteoLtAPI()
    coordinator = MeteoLtUpdateCoordinator(hass, client, place_code, entry)

    try:
        await coordinator.async_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Failed to connect to Meteo.lt API for {place_code}"
        ) from err

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady(f"Failed to fetch initial data for {place_code}")

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MeteoLtConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
