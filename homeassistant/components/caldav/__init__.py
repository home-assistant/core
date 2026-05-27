"""The caldav component."""

import asyncio
from dataclasses import dataclass
import logging

import caldav
from caldav.lib.error import AuthorizationError, DAVError
import requests

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

from .const import TIMEOUT
from .coordinator import MAX_CONCURRENT_REQUESTS, close_idle_connections


@dataclass
class CalDavRuntimeData:
    """Runtime data shared between caldav platforms."""

    client: caldav.DAVClient
    request_semaphore: asyncio.Semaphore


type CalDavConfigEntry = ConfigEntry[CalDavRuntimeData]

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [Platform.CALENDAR, Platform.TODO]


async def async_setup_entry(hass: HomeAssistant, entry: CalDavConfigEntry) -> bool:
    """Set up CalDAV from a config entry."""
    client = caldav.DAVClient(
        entry.data[CONF_URL],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        ssl_verify_cert=entry.data[CONF_VERIFY_SSL],
        timeout=TIMEOUT,
    )
    try:
        await hass.async_add_executor_job(client.principal)
    except AuthorizationError as err:
        if err.reason == "Unauthorized":
            raise ConfigEntryAuthFailed("Credentials error from CalDAV server") from err
        # AuthorizationError can be raised if the url is incorrect or
        # on some other unexpected server response.
        _LOGGER.warning("Unexpected CalDAV server response: %s", err)
        return False
    except requests.Timeout as err:
        raise ConfigEntryNotReady("Timeout connecting to CalDAV server") from err
    except requests.ConnectionError as err:
        raise ConfigEntryNotReady("Connection error from CalDAV server") from err
    except DAVError as err:
        raise ConfigEntryNotReady("CalDAV client error") from err

    entry.runtime_data = CalDavRuntimeData(
        client=client,
        request_semaphore=asyncio.Semaphore(MAX_CONCURRENT_REQUESTS),
    )

    async def _close_client_session() -> None:
        """Tear down the underlying HTTP session at entry unload.

        ``session.close()`` is synchronous and can block on socket teardown,
        so dispatch it to the executor rather than running on the event loop.
        """
        await hass.async_add_executor_job(close_idle_connections, client)

    entry.async_on_unload(_close_client_session)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
