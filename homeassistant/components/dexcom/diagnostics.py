"""Diagnostics support for the Dexcom integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_UNIQUE_ID, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .coordinator import DexcomConfigEntry

# The entry title and unique ID are the Dexcom username.
TO_REDACT = {CONF_PASSWORD, CONF_UNIQUE_ID, CONF_USERNAME, "title"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DexcomConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    reading: dict[str, Any] | None = None
    if (glucose := coordinator.data) is not None:
        reading = {
            "timestamp": glucose.datetime.isoformat(),
            "age_seconds": round((dt_util.utcnow() - glucose.datetime).total_seconds()),
        }
    return {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "reading": reading,
    }
