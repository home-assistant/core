"""Integration for Apple's WeatherKit API."""

from __future__ import annotations

from apple_weatherkit.client import (
    WeatherKitApiClient,
    WeatherKitApiClientAuthenticationError,
    WeatherKitApiClientError,
)

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_KEY_ID, CONF_KEY_PEM, CONF_SERVICE_ID, CONF_TEAM_ID, LOGGER
from .coordinator import WeatherKitConfigEntry, WeatherKitDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, entry: WeatherKitConfigEntry) -> bool:
    """Set up this integration using UI."""
    coordinator = WeatherKitDataUpdateCoordinator(
        hass=hass,
        config_entry=entry,
        client=WeatherKitApiClient(
            key_id=entry.data[CONF_KEY_ID],
            service_id=entry.data[CONF_SERVICE_ID],
            team_id=entry.data[CONF_TEAM_ID],
            key_pem=entry.data[CONF_KEY_PEM],
            session=async_get_clientsession(hass),
        ),
    )

    try:
        await coordinator.update_supported_data_sets()
    except WeatherKitApiClientAuthenticationError as ex:
        LOGGER.error("Authentication error initializing integration: %s", ex)
        return False
    except WeatherKitApiClientError as ex:
        raise ConfigEntryNotReady from ex

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WeatherKitConfigEntry) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
