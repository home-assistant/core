"""The Sonarr component."""
from __future__ import annotations

from datetime import timedelta

from aiopyarr import ArrAuthenticationException, ArrException
from aiopyarr.models.host_configuration import PyArrHostConfiguration
from aiopyarr.sonarr_client import SonarrClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_BASE_PATH,
    CONF_UPCOMING_DAYS,
    CONF_WANTED_MAX_ITEMS,
    DATA_HOST_CONFIG,
    DATA_SONARR,
    DATA_SYSTEM_STATUS,
    DEFAULT_UPCOMING_DAYS,
    DEFAULT_WANTED_MAX_ITEMS,
    DOMAIN,
)

PLATFORMS = [Platform.SENSOR]
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sonarr from a config entry."""
    if not entry.options:
        options = {
            CONF_UPCOMING_DAYS: entry.data.get(
                CONF_UPCOMING_DAYS, DEFAULT_UPCOMING_DAYS
            ),
            CONF_WANTED_MAX_ITEMS: entry.data.get(
                CONF_WANTED_MAX_ITEMS, DEFAULT_WANTED_MAX_ITEMS
            ),
        }
        hass.config_entries.async_update_entry(entry, options=options)

    base_api_path = entry.data[CONF_BASE_PATH]

    if base_api_path in ("", "/", "/api"):
        base_api_path = None

    host_configuration = PyArrHostConfiguration(
        api_token=entry.data[CONF_API_KEY],
        ipaddress=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        ssl=entry.data[CONF_SSL],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
        base_api_path=base_api_path,
    )

    sonarr = SonarrClient(
        host_configuration=host_configuration,
        session=async_get_clientsession(hass),
    )

    try:
        system_status = await sonarr.async_get_system_status()
    except ArrAuthenticationException as err:
        raise ConfigEntryAuthFailed(
            "API Key is no longer valid. Please reauthenticate"
        ) from err
    except ArrException as err:
        raise ConfigEntryNotReady from err

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_HOST_CONFIG: host_configuration,
        DATA_SONARR: sonarr,
        DATA_SYSTEM_STATUS: system_status,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
