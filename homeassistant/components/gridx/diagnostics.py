"""Diagnostics support for the gridX integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import GridxConfigEntry

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME, "applianceID"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: GridxConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a gridX config entry."""
    # Key by position so the diagnostics do not expose the system UUIDs.
    live_data = {
        f"system_{index}": data
        for index, data in enumerate(entry.runtime_data.data.values(), start=1)
    }
    return {
        "config_entry": async_redact_data(dict(entry.data), TO_REDACT),
        "live_data": async_redact_data(live_data, TO_REDACT),
    }
