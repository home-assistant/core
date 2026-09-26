"""Plane titles for the Forecast.Solar integration."""

from collections.abc import Mapping
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import (
    CONF_AZIMUTH,
    CONF_AZIMUTH_SENSOR,
    CONF_DECLINATION,
    CONF_DECLINATION_SENSOR,
    CONF_MODULES_POWER,
    DOMAIN,
)

# The UI stores an azimuth of 0-360, while a compass may report -180..180.
ANGLE_RANGES: dict[str, tuple[float, float]] = {
    CONF_DECLINATION_SENSOR: (0, 90),
    CONF_AZIMUTH_SENSOR: (-180, 360),
}


class SensorUpdateFailed(UpdateFailed):
    """Raised when a plane sensor can't be read, before the API is called."""


def sensor_angle(hass: HomeAssistant, entity_id: str, sensor_key: str) -> float:
    """Return a sensor's angle, raising if it can't be used."""
    min_value, max_value = ANGLE_RANGES[sensor_key]
    if (sensor := hass.states.get(entity_id)) is None:
        raise SensorUpdateFailed(
            translation_domain=DOMAIN,
            translation_key="sensor_no_state",
            translation_placeholders={"entity_id": entity_id},
        )

    try:
        value = float(sensor.state)
    except ValueError:
        value = None
    if value is None or not min_value <= value <= max_value:
        raise SensorUpdateFailed(
            translation_domain=DOMAIN,
            translation_key="sensor_invalid",
            translation_placeholders={
                "entity_id": entity_id,
                "state": sensor.state,
                "min": str(min_value),
                "max": str(max_value),
            },
        )
    return value


def _angle_label(
    hass: HomeAssistant, data: Mapping[str, Any], value_key: str, sensor_key: str
) -> str:
    """Label a plane angle by its sensor's name, or by its fixed value."""
    if (entity_id := data.get(sensor_key)) is None:
        return f"{data[value_key]}°"
    state = hass.states.get(entity_id)
    return f"{state.name if state else entity_id} (sensor)"


def plane_title(hass: HomeAssistant, data: Mapping[str, Any]) -> str:
    """Build a plane subentry title from its declination/azimuth/power."""
    declination = _angle_label(hass, data, CONF_DECLINATION, CONF_DECLINATION_SENSOR)
    azimuth = _angle_label(hass, data, CONF_AZIMUTH, CONF_AZIMUTH_SENSOR)
    return f"{declination} / {azimuth} / {data[CONF_MODULES_POWER]}W"
