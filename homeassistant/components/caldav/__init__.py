"""The caldav component."""

import logging

import caldav
from caldav.lib.error import AuthorizationError, DAVError
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CalDAV from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    client = caldav.DAVClient(
        entry.data[CONF_URL],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )
    try:
        await hass.async_add_executor_job(client.principal)
    except AuthorizationError as err:
        if err.reason == "Unauthorized":
            raise ConfigEntryAuthFailed("Credentials error from CalDAV server") from err
        _LOGGER.warning("Unexpected CalDAV server response: %s", err)
        return False
    except requests.ConnectionError as err:
        _LOGGER.warning("Connection Error connecting to CalDAV server: %s", err)
        raise ConfigEntryNotReady("Connection error from CalDAV server") from err
    except DAVError as err:
        _LOGGER.warning("CalDAV client error: %s", err)
        raise ConfigEntryNotReady("CalDAV client error") from err

    hass.data[DOMAIN][entry.entry_id] = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
