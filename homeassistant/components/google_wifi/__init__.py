"""The google_wifi component."""

from googlewifiapi import GoogleWifiAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import AnyDeviceEntry

from .const import DOMAIN as DOMAIN
from .coordinator import GoogleWifiCoordinator

_PLATFORMS = [Platform.SENSOR]

type GoogleWifiConfigEntry = ConfigEntry[GoogleWifiCoordinator]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoogleWifiConfigEntry,
) -> None:
    """Set up Google Wifi from a config entry."""
    api = GoogleWifiAPI(entry.data[CONF_HOST], sess=async_get_clientsession(hass))
    coordinator = GoogleWifiCoordinator(hass, config_entry=entry, api=api)

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: GoogleWifiConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, _PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: GoogleWifiConfigEntry, device_entry: AnyDeviceEntry
) -> bool:
    """Allow removing a device that is no longer connected."""
    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN and identifier[1] in entry.runtime_data.data.devices
    )
