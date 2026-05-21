"""Provide diagnostics for OpenEVSE."""

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


def _to_json_safe(val: Any, seen: set[int] | None = None, depth: int = 0) -> Any:
    """Coerce value to be JSON-serializable.

    Top-level callables on the charger object are skipped entirely in the main
    diagnostics loop. For nested structures (lists, dicts, tuples, sets), any
    encountered callable elements are coerced to None here to preserve the
    structure while remaining JSON-safe.
    """
    if isinstance(val, (str, int, float, bool)) or val is None:
        return val

    if depth > 20:
        return f"<Depth limit exceeded: {type(val).__name__}>"

    if seen is None:
        seen = set()

    val_id = id(val)
    if val_id in seen:
        return f"<Circular reference detected: {type(val).__name__}>"

    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, Enum):
        return val.value
    if isinstance(val, (set, frozenset)):
        seen.add(val_id)
        try:
            return [_to_json_safe(v, seen, depth + 1) for v in sorted(val, key=str)]
        finally:
            seen.remove(val_id)
    if isinstance(val, (list, tuple)):
        seen.add(val_id)
        try:
            return [_to_json_safe(v, seen, depth + 1) for v in val]
        finally:
            seen.remove(val_id)
    if isinstance(val, dict):
        seen.add(val_id)
        try:
            res = {}
            for k in sorted(val, key=str):
                if isinstance(k, str):
                    key_str = k
                elif isinstance(k, Enum):
                    key_str = f"{type(k).__name__}.{k.name}"
                else:
                    key_str = f"<{type(k).__name__}: {k}>"
                res[key_str] = _to_json_safe(val[k], seen, depth + 1)
            return res
        finally:
            seen.remove(val_id)
    if callable(val):
        return None
    return f"<{type(val).__name__} object>"


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
        except Exception as err:  # noqa: BLE001
            charger_data[prop] = f"Error: {type(err).__name__}"
            continue

        # Top-level callables on the charger object are omitted from diagnostics.
        # Any nested callables within collections are coerced to None by _to_json_safe.
        if callable(val):
            continue

        charger_data[prop] = _to_json_safe(val)

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), REDACT_CONFIG_DATA),
        "charger": charger_data,
    }
