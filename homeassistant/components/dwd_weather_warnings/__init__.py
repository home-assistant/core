"""The dwd_weather_warnings component."""

from __future__ import annotations

from dwdwfsapi import DwdWeatherWarningsAPI
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_REGION_DEVICE_TRACKER,
    CONF_REGION_IDENTIFIER,
    DOMAIN,
    LOGGER,
    PLATFORMS,
)
from .coordinator import DwdWeatherWarningsCoordinator
from .util import get_position_data


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    region_identifier: str = entry.data.get(CONF_REGION_IDENTIFIER, None)
    device_tracker: str = entry.data.get(CONF_REGION_DEVICE_TRACKER, None)

    # Initialize the API and coordinator based on the specified data.
    if region_identifier is not None:
        api = await hass.async_add_executor_job(
            DwdWeatherWarningsAPI, region_identifier
        )
    elif device_tracker is not None:
        try:
            registry = er.async_get(hass)
            device_tracker = er.async_validate_entity_id(registry, device_tracker)
        except vol.Invalid:
            # The entity/UUID is invalid or not associated with an entity registry item.
            LOGGER.error(
                "Failed to setup dwd_weather_warnings for unknown entity %s",
                device_tracker,
            )
            return False

        position = get_position_data(hass, device_tracker)
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
