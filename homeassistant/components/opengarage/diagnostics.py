"""Diagnostics for OpenGarage."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import OpenGarageConfigEntry

TO_REDACT = {"name", "mac", "cid", "dkey", "device_key", "_raw"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OpenGarageConfigEntry
) -> dict[str, Any]:
    """Return normalized state and firmware fields with identifiers redacted."""
    return async_redact_data(entry.runtime_data.data.to_dict(), TO_REDACT)
