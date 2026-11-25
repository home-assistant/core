"""The caldav component."""

from dataclasses import dataclass
from functools import partial

from caldav.davclient import DAVClient
from caldav.lib.error import AuthorizationError, DAVError
from caldav.lib.http_sync import requests as caldav_requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)

from .api import CalDavCalendar, get_calendars
from .const import DOMAIN, TIMEOUT


@dataclass
class CalDavData:
    """The client of a config entry and the calendars it found."""

    client: DAVClient
    calendars: list[CalDavCalendar]


type CalDavConfigEntry = ConfigEntry[CalDavData]


PLATFORMS: list[Platform] = [Platform.CALENDAR, Platform.TODO]


async def async_setup_entry(hass: HomeAssistant, entry: CalDavConfigEntry) -> None:
    """Set up CalDAV from a config entry."""
    client = await hass.async_add_executor_job(
        partial(
            DAVClient,
            entry.data[CONF_URL],
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            ssl_verify_cert=entry.data[CONF_VERIFY_SSL],
            timeout=TIMEOUT,
        )
    )
    try:
        calendars = await hass.async_add_executor_job(
            get_calendars, client, {"VEVENT", "VTODO"}
        )
    except AuthorizationError as err:
        if err.reason == "Unauthorized":
            raise ConfigEntryAuthFailed("Credentials error from CalDAV server") from err
        # AuthorizationError can be raised if the url is incorrect or
        # on some other unexpected server response.
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="unexpected_response",
        ) from err
    except caldav_requests.exceptions.Timeout as err:
        raise ConfigEntryNotReady("Timeout connecting to CalDAV server") from err
    except caldav_requests.exceptions.ConnectionError as err:
        raise ConfigEntryNotReady("Connection error from CalDAV server") from err
    except DAVError as err:
        raise ConfigEntryNotReady("CalDAV client error") from err

    entry.runtime_data = CalDavData(client, calendars)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: CalDavConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
