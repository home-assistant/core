"""Diagnostics support for Glances."""

from typing import Any

from homeassistant.const import CONF_PORT, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from .coordinator import GlancesConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GlancesConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "config_entry": {
            key: entry.data[key] for key in (CONF_PORT, CONF_SSL, CONF_VERIFY_SSL)
        },
        "api_version": coordinator.api.version,
        "data": {
            key: value for key, value in coordinator.data.items() if key != "computed"
        },
    }
