"""Provides diagnostics for local calendar."""

import datetime
from typing import Any

from ical.diagnostics import redact_ics

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    payload: dict[str, Any] = {
        "now": dt_util.now().isoformat(),
        "timezone": str(dt_util.DEFAULT_TIME_ZONE),
        "system_timezone": str(datetime.datetime.utcnow().astimezone().tzinfo),
    }
    store = hass.data[DOMAIN][config_entry.entry_id]
    ics = await store.async_load()
    payload["ics"] = "\n".join(redact_ics(ics))
    return payload
