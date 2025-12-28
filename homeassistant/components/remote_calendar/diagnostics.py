"""Provides diagnostics for the remote calendar."""

import datetime
from typing import Any

from ical.diagnostics import redact_ics

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import RemoteCalendarConfigEntry

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME, CONF_URL}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RemoteCalendarConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    payload: dict[str, Any] = {
        "now": dt_util.now().isoformat(),
        "timezone": str(dt_util.get_default_time_zone()),
        "system_timezone": str(datetime.datetime.now().astimezone().tzinfo),
        "entry_data": async_redact_data(entry.data, TO_REDACT),
    }
    payload["ics"] = "\n".join(redact_ics(coordinator.ics))
    return payload
