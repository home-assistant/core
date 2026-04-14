"""Diagnostics support for the BLANCO integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import BlancoConfigEntry
from .const import CONF_APP_ID, CONF_DEV_ID, CONF_SERIAL, CONF_TOKEN

# Keys whose values must never appear unredacted in a diagnostics download.
# Applied to both config entry data and coordinator API response snapshots.
_REDACT: frozenset[str] = frozenset(
    {
        # Config entry credentials
        CONF_TOKEN,  # "token"
        CONF_APP_ID,  # "app_id"
        CONF_DEV_ID,  # "devId"
        CONF_SERIAL,  # "serial"
        # Common field names that may appear in raw API responses
        "token",
        "app_id",
        "dev_id",
        "devId",
        "serial",
    }
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: BlancoConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a BLANCO config entry.

    All sensitive values (token, app_id, dev_id, serial) are redacted in
    both the config entry data and the coordinator API response snapshot.
    The coordinator runtime state is included so that support requests can
    be resolved without requiring manual log extraction.
    """
    coordinator = entry.runtime_data

    return {
        "config_entry": async_redact_data(dict(entry.data), _REDACT),
        "coordinator": {
            "dev_type": str(coordinator.dev_type),
            "last_action_ts": coordinator.last_action_ts,
            "last_dispensing_ml": coordinator.last_dispensing_ml,
            "water_totals_ml": coordinator.water_totals_ml,
            "data": async_redact_data(coordinator.data or {}, _REDACT),
        },
    }
