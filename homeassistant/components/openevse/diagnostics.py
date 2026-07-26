"""Provide diagnostics for OpenEVSE."""

import asyncio
from datetime import date, datetime
from enum import Enum
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import OpenEVSEConfigEntry

REDACT_CONFIG_DATA = {CONF_PASSWORD, CONF_USERNAME}
CHARGER_PROPERTIES = (
    "status",
    "vehicle",
    "mode",
    "charge_mode",
    "divertmode",
    "manual_override",
    "ota_update",
    "service_level",
    "charge_time_elapsed",
    "vehicle_eta",
    "charging_current",
    "charging_voltage",
    "charging_power",
    "current_power",
    "current_capacity",
    "max_current",
    "min_amps",
    "max_amps",
    "max_current_soft",
    "available_current",
    "smoothed_available_current",
    "charge_rate",
    "ambient_temperature",
    "ir_temperature",
    "rtc_temperature",
    "esp_temperature",
    "usage_session",
    "usage_total",
    "total_day",
    "total_week",
    "total_month",
    "total_year",
    "vehicle_soc",
    "vehicle_range",
    "wifi_signal",
    "shaper_live_power",
    "shaper_available_current",
    "shaper_max_power",
    "gfi_trip_count",
    "no_gnd_trip_count",
    "stuck_relay_trip_count",
    "uptime",
    "freeram",
    "wifi_firmware",
    "openevse_firmware",
)


def _to_json_safe(val: Any) -> Any:
    """Coerce value to be JSON-serializable."""
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, Enum):
        return val.value
    return val


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant, config_entry: OpenEVSEConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data
    charger = coordinator.charger

    charger_data: dict[str, Any] = {}

    for prop in CHARGER_PROPERTIES:
        try:
            val = getattr(charger, prop)
        except AttributeError:
            continue
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001
            charger_data[prop] = f"Error: {type(err).__name__}"
            continue

        # Top-level callables on the charger object are omitted from diagnostics.
        if callable(val):
            continue

        charger_data[prop] = _to_json_safe(val)

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), REDACT_CONFIG_DATA),
        "charger": charger_data,
    }
