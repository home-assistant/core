"""The Google Wifi integration."""

from googlewifiapi import GoogleWifiAPI

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import GoogleWifiConfigEntry, GoogleWifiCoordinator

_PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: GoogleWifiConfigEntry) -> None:
    """Set up Google Wifi from a config entry."""
    api = GoogleWifiAPI(entry.data[CONF_HOST], sess=async_get_clientsession(hass))
    coordinator = GoogleWifiCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: GoogleWifiConfigEntry
) -> None:
    """Unload a Google Wifi config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, _PLATFORMS)
    await entry.runtime_data.async_shutdown()
