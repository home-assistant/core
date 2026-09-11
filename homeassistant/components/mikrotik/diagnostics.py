"""Diagnostics support for Mikrotik router."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .coordinator import MikrotikConfigEntry

TO_REDACT = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MikrotikConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    coordinator = entry.runtime_data

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "device_info": {
            "model": coordinator.api.model,
            "firmware": coordinator.api.firmware,
            "support_capman": coordinator.api.support_capsman,
            "support_wifi": coordinator.api.support_wifi,
            "support_wireless": coordinator.api.support_wireless,
            "support_wifiwave2": coordinator.api.support_wifiwave2,
            "sensors": coordinator.api.sensors,
            "system": coordinator.api.system,
            "last_update success": coordinator.last_update_success,
            "last_exception": repr(coordinator.last_exception),
        },
    }
