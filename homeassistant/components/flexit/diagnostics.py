"""Diagnostics support for Flexit."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import FlexitConfigEntry

TO_REDACT = {CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FlexitConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    device = entry.runtime_data.device
    measurements = device.measurements

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "data": {
            "target_temperature": device.target_temperature,
            "current_temperature": measurements.supply_air_temperature,
            "outdoor_air_temperature": measurements.outdoor_air_temperature,
            "fan_mode": device.fan_mode.name if device.fan_mode else None,
            "activity": device.activity.name if device.activity else None,
            "filter_running_hours": measurements.filter_running_hours,
            "filter_alarm": measurements.filter_alarm,
            "heat_exchanger_regulation": measurements.heat_exchanger_regulation,
            "electric_heater_regulation": measurements.electric_heater_regulation,
            "electric_heater_enabled": measurements.electric_heater_enabled,
            "cooling_regulation": measurements.cooling_regulation,
            "actual_air_speed": measurements.actual_air_speed,
        },
    }
