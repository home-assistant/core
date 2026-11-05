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
    config_entry = async_redact_data(entry.as_dict(), TO_REDACT)
    # runtime_data is not set when setup failed, which is when diagnostics help most
    if (coordinator := getattr(entry, "runtime_data", None)) is None:
        return {
            "config_entry": config_entry,
            "last_update_success": None,
            "reading": None,
        }
    reading: dict[str, Any] | None = None
    if (glucose := coordinator.data) is not None:
        reading = {
            "value": glucose.value,
            "mmol_l": glucose.mmol_l,
            "trend": glucose.trend,
            "trend_description": glucose.trend_description,
            "timestamp": glucose.datetime.isoformat(),
            "age_seconds": round((dt_util.utcnow() - glucose.datetime).total_seconds()),
        }
    return {
        "config_entry": config_entry,
        "last_update_success": coordinator.last_update_success,
        "reading": reading,
    }
