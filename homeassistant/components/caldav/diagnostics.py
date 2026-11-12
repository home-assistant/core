"""Diagnostics support for CalDAV."""

from typing import Any, cast

from caldav.collection import Calendar
from caldav.davclient import DAVClient
from caldav.lib.error import DAVError
from caldav.lib.http_sync import requests as caldav_requests

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import CalDavConfigEntry

TO_REDACT = {CONF_PASSWORD, CONF_URL, CONF_USERNAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: CalDavConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    payload: dict[str, Any] = {
        "now": dt_util.now().isoformat(),
        "timezone": str(dt_util.get_default_time_zone()),
        "system_timezone": str(dt_util.naive_now().astimezone().tzinfo),
        "data": async_redact_data(entry.data, TO_REDACT),
    }
    if entry.state is ConfigEntryState.LOADED:
        try:
            payload["calendars"] = await hass.async_add_executor_job(
                _get_calendars, entry.runtime_data
            )
        except (
            caldav_requests.exceptions.ConnectionError,
            caldav_requests.exceptions.Timeout,
            DAVError,
        ) as err:
            # The error message can contain the server URL and the username
            payload["calendars_error"] = type(err).__name__
    return payload


def _get_calendars(client: DAVClient) -> list[dict[str, Any]]:
    """Return whether each calendar has a name and which components it supports."""
    calendars = cast(list[Calendar], client.get_principal().get_calendars())
    return [
        {
            "has_name": bool(calendar.get_display_name()),
            "supported_components": sorted(
                cast(list[str], calendar.get_supported_components())
            ),
        }
        for calendar in calendars
    ]
