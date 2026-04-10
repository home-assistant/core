"""The Tomorrow.io integration."""

from __future__ import annotations

from pytomorrowio import TomorrowioV4

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import (
    TomorrowioConfigEntry,
    TomorrowioDataUpdateCoordinator,
    async_get_entries_by_api_key,
)

PLATFORMS = [SENSOR_DOMAIN, WEATHER_DOMAIN]


async def async_setup_entry(hass: HomeAssistant, entry: TomorrowioConfigEntry) -> bool:
    """Set up Tomorrow.io API from a config entry."""
    api_key = entry.data[CONF_API_KEY]
    # If another entry already has a coordinator for this API key, reuse it.
    # Otherwise create a new one.
    coordinator: TomorrowioDataUpdateCoordinator | None = None
    for other_entry in async_get_entries_by_api_key(hass, api_key, exclude_entry=entry):
        if hasattr(other_entry, "runtime_data"):
            coordinator = other_entry.runtime_data
            break

    if coordinator is None:
        session = async_get_clientsession(hass)
        # we will not use the class's lat and long so we can pass in garbage
        # lats and longs
        api = TomorrowioV4(api_key, 361.0, 361.0, unit_system="metric", session=session)
        coordinator = TomorrowioDataUpdateCoordinator(hass, entry, api)

    entry.runtime_data = coordinator

    await coordinator.async_setup_entry(entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: TomorrowioConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    await config_entry.runtime_data.async_unload_entry(config_entry)

    return unload_ok
