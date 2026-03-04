"""The caldav component."""

import logging

import caldav
from caldav.lib.error import AuthorizationError, DAVError
import requests
from requests.adapters import HTTPAdapter

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

type CalDavConfigEntry = ConfigEntry[caldav.DAVClient]

_LOGGER = logging.getLogger(__name__)

CONNECTION_POOL_SIZE = 20

PLATFORMS: list[Platform] = [Platform.CALENDAR, Platform.TODO]


async def async_setup_entry(hass: HomeAssistant, entry: CalDavConfigEntry) -> bool:
    """Set up CalDAV from a config entry."""
    client = caldav.DAVClient(
        entry.data[CONF_URL],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        ssl_verify_cert=entry.data[CONF_VERIFY_SSL],
        timeout=30,
    )
    # Increase the connection pool size to prevent "Connection pool is
    # full, discarding connection" warnings when many calendar and todo
    # entities poll the same CalDAV server concurrently. The default
    # urllib3 pool size of 10 is easily exceeded with 10+ calendars.
    # See: https://github.com/home-assistant/core/issues/117927
    adapter = HTTPAdapter(
        pool_connections=CONNECTION_POOL_SIZE, pool_maxsize=CONNECTION_POOL_SIZE
    )
    client.session.mount("https://", adapter)
    client.session.mount("http://", adapter)
    try:
        await hass.async_add_executor_job(client.principal)
    except AuthorizationError as err:
        if err.reason == "Unauthorized":
            raise ConfigEntryAuthFailed("Credentials error from CalDAV server") from err
        # AuthorizationError can be raised if the url is incorrect or
        # on some other unexpected server response.
        _LOGGER.warning("Unexpected CalDAV server response: %s", err)
        return False
    except requests.ConnectionError as err:
        raise ConfigEntryNotReady("Connection error from CalDAV server") from err
    except DAVError as err:
        raise ConfigEntryNotReady("CalDAV client error") from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
