"""Diagnostics support for Ping."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import DATA_PRIVILEGED_KEY
from .coordinator import PingConfigEntry

PING_METHODS = {
    None: "ping_command",
    True: "icmp_privileged",
    False: "icmp_unprivileged",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PingConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "options": async_redact_data(entry.options, {CONF_HOST}),
        "ping_method": PING_METHODS[hass.data[DATA_PRIVILEGED_KEY]],
        "last_update_success": coordinator.last_update_success,
        "is_alive": coordinator.data.is_alive,
        "data": coordinator.data.data,
    }
