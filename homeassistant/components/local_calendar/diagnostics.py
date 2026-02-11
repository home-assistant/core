"""Provides diagnostics for local calendar."""

import datetime
from typing import Any

from ical.diagnostics import redact_ics

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import LocalCalendarConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: LocalCalendarConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    payload: dict[str, Any] = {
        "now": dt_util.now().isoformat(),
        "timezone": str(dt_util.get_default_time_zone()),
        "system_timezone": str(datetime.datetime.now().astimezone().tzinfo),
    }
    store = config_entry.runtime_data
    ics = await store.async_load()
    payload["ics"] = "\n".join(redact_ics(ics))
    return payload
