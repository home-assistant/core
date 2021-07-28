"""The Sonarr component."""
from __future__ import annotations

from datetime import timedelta
import logging

from sonarr import Sonarr, SonarrAccessRestricted, SonarrError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_BASE_PATH,
    CONF_UPCOMING_DAYS,
    CONF_WANTED_MAX_ITEMS,
    DATA_SONARR,
    DEFAULT_UPCOMING_DAYS,
    DEFAULT_WANTED_MAX_ITEMS,
    DOMAIN,
)

PLATFORMS = ["sensor"]
SCAN_INTERVAL = timedelta(seconds=30)
_LOGGER = logging.getLogger(__name__)


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

    sonarr = Sonarr(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        api_key=entry.data[CONF_API_KEY],
        base_path=entry.data[CONF_BASE_PATH],
        session=async_get_clientsession(hass),
        tls=entry.data[CONF_SSL],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
    )

    try:
        await sonarr.update()
    except SonarrAccessRestricted as err:
        raise ConfigEntryAuthFailed(
            "API Key is no longer valid. Please reauthenticate"
        ) from err
    except SonarrError as err:
        raise ConfigEntryNotReady from err

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_SONARR: sonarr,
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
