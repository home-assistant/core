"""The dwd_weather_warnings component."""

from __future__ import annotations

from dwdwfsapi import DwdWeatherWarningsAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_REGION_DEVICE_TRACKER,
    CONF_REGION_IDENTIFIER,
    DOMAIN,
    LOGGER,
    PLATFORMS,
)
from .coordinator import DwdWeatherWarningsCoordinator
from .exceptions import EntityNotFoundError
from .util import get_position_data


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    # Initialize the API and coordinator based on the specified data.
    if (region_identifier := entry.data.get(CONF_REGION_IDENTIFIER)) is not None:
        api = await hass.async_add_executor_job(
            DwdWeatherWarningsAPI, region_identifier
        )
    else:
        device_tracker = entry.data.get(CONF_REGION_DEVICE_TRACKER)

        try:
            position = get_position_data(hass, device_tracker)
        except (EntityNotFoundError, AttributeError) as err:
            # The provided device_tracker is not available or missing required attributes.
            LOGGER.error(f"Failed to setup dwd_weather_warnings: {repr(err)}")
            return False

        api = await hass.async_add_executor_job(DwdWeatherWarningsAPI, position)

    coordinator = DwdWeatherWarningsCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
