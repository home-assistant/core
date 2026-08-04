"""Diagnostics support for Growatt Server."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_UNIQUE_ID, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_PLANT_ID
from .coordinator import GrowattConfigEntry

try:
    # See the matching import in __init__.py for why this is optional.
    from . import _build_info
except ImportError:
    _build_info = None

TO_REDACT = {
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
    CONF_UNIQUE_ID,
    CONF_PLANT_ID,
    "user_id",
    "deviceSn",
    "device_sn",
}

# Allowlist of safe telemetry fields from the total coordinator.
# Monetary fields (plantMoneyText, totalMoneyText, currency) are intentionally
# excluded to avoid leaking financial data under unpredictable key names.
_TOTAL_SAFE_KEYS = frozenset(
    {
        # Classic API keys
        "todayEnergy",
        "totalEnergy",
        "invTodayPpv",
        "nominalPower",
        # V1 API keys (aliases used after normalisation in coordinator)
        "today_energy",
        "total_energy",
        "current_power",
    }
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: GrowattConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = config_entry.runtime_data
    total_data = runtime_data.total_coordinator.data or {}
    return async_redact_data(
        {
            "build": (
                {
                    "commit": _build_info.BUILD_COMMIT,
                    "deployed": _build_info.BUILD_TIME,
                }
                if _build_info is not None
                else None
            ),
            "config_entry": config_entry.as_dict(),
            "total_coordinator": {
                k: v for k, v in total_data.items() if k in _TOTAL_SAFE_KEYS
            },
            "devices": [
                {
                    "device_sn": device_sn,
                    "device_type": coordinator.device_type,
                    "data": coordinator.data,
                }
                for device_sn, coordinator in runtime_data.devices.items()
            ],
        },
        TO_REDACT,
    )
