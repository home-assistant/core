"""Provides diagnostics for the remote calendar."""

import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.const import CONF_URL
from . import RemoteCalendarConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RemoteCalendarConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "now": dt_util.now().isoformat(),
        "timezone": str(dt_util.get_default_time_zone()),
        "system_timezone": str(datetime.datetime.now().astimezone().tzinfo),
        "url": entry.data[CONF_URL],
        "data": dict(coordinator.data),
    }
