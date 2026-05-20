"""Diagnostics support for AirTouch 3."""

from typing import Any

from pyairtouch3 import Aircon, AirtouchZone

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import AirTouch3ConfigEntry

TO_REDACT = {CONF_HOST}


def _zone_diagnostics(zone: AirtouchZone) -> dict[str, Any]:
    """Return diagnostics for a zone."""
    sensor = zone.sensor
    return {
        "id": zone.id,
        "name": zone.name,
        "status": zone.status.name,
        "touch_pad_temperature": zone.touch_pad_temperature,
        "desired_temperature": zone.desired_temperature,
        "sensor": {
            "available": bool(sensor and sensor.is_available),
            "current_temperature": (
                sensor.current_temperature
                if sensor is not None and sensor.is_available
                else None
            ),
        },
    }


def _aircon_diagnostics(aircon: Aircon | None) -> dict[str, Any] | None:
    """Return diagnostics for AirTouch data."""
    if aircon is None:
        return None

    return {
        "ac_id": aircon.ac_id,
        "brand_id": aircon.brand_id,
        "status": aircon.status,
        "fan_speed": aircon.fan_speed,
        "mode": aircon.mode.name,
        "room_temperature": aircon.room_temperature,
        "desired_temperature": aircon.desired_temperature,
        "zone_count": len(aircon.zones),
        "zones": [_zone_diagnostics(zone) for zone in aircon.zones],
    }


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant, entry: AirTouch3ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return async_redact_data(
        {
            "config_entry": {
                "data": dict(entry.data),
                "options": dict(entry.options),
            },
            "airtouch3": _aircon_diagnostics(coordinator.data),
        },
        TO_REDACT,
    )
