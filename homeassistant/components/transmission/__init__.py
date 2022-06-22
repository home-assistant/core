"""Support for the Transmission BitTorrent client API."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    SERVICE_ADD_TORRENT,
    SERVICE_REMOVE_TORRENT,
    SERVICE_START_TORRENT,
    SERVICE_STOP_TORRENT,
)
from .coordinator import TransmissionDataUpdateCoordinator, get_api
from .errors import AuthenticationError, CannotConnect, UnknownError

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

PLATFORMS = [Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Transmission Component."""

    try:
        api = await get_api(hass, dict(config_entry.data))
    except CannotConnect as error:
        raise ConfigEntryNotReady from error
    except (AuthenticationError, UnknownError) as error:
        raise ConfigEntryAuthFailed from error

    coordinator = TransmissionDataUpdateCoordinator(hass, config_entry, api)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Transmission Entry from config_entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        hass.data[DOMAIN].pop(config_entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_ADD_TORRENT)
            hass.services.async_remove(DOMAIN, SERVICE_REMOVE_TORRENT)
            hass.services.async_remove(DOMAIN, SERVICE_START_TORRENT)
            hass.services.async_remove(DOMAIN, SERVICE_STOP_TORRENT)
            del hass.data[DOMAIN]

    return unload_ok
