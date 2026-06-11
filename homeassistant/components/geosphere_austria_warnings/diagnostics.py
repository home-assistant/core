"""Diagnostics support for the GeoSphere Austria Warnings integration."""

from dataclasses import asdict
from typing import Any

from pygeosphere_warnings import WeatherWarning

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from .coordinator import GeoSphereConfigEntry

TO_REDACT = {CONF_LATITUDE, CONF_LONGITUDE}


def _serialize_warning(warning: WeatherWarning) -> dict[str, Any]:
    """Return a JSON serializable representation of a warning."""
    return {
        "warning_id": warning.warning_id,
        "change_id": warning.change_id,
        "course_id": warning.course_id,
        "warning_type": warning.warning_type.name,
        "level": warning.level.name,
        "start": warning.start.isoformat(),
        "end": warning.end.isoformat(),
        "text": warning.text,
        "impacts": warning.impacts,
        "recommendations": warning.recommendations,
        "meteo_text": warning.meteo_text,
        "update_reason": warning.update_reason,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GeoSphereConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data.data
    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "municipality": asdict(data.location_warnings.municipality),
        "warnings": [
            _serialize_warning(warning) for warning in data.location_warnings.warnings
        ],
        "thunderstorm_intensity": data.thunderstorm_intensity,
    }
