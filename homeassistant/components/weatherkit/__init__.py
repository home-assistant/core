"""Integration for Apple's WeatherKit API."""
from __future__ import annotations

from apple_weatherkit.client import WeatherKitApiClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_KEY_ID, CONF_KEY_PEM, CONF_SERVICE_ID, CONF_TEAM_ID, DOMAIN
from .coordinator import WeatherKitDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator = WeatherKitDataUpdateCoordinator(
        hass=hass,
        client=WeatherKitApiClient(
            key_id=entry.data[CONF_KEY_ID],
            service_id=entry.data[CONF_SERVICE_ID],
            team_id=entry.data[CONF_TEAM_ID],
            key_pem=entry.data[CONF_KEY_PEM],
            session=async_get_clientsession(hass),
        ),
    )

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
