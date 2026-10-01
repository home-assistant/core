"""Plane angle and title helpers for the Forecast.Solar integration."""

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

SENSOR_KEYS = (CONF_DECLINATION_SENSOR, CONF_AZIMUTH_SENSOR)

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
            translation_placeholders={"entity_id": entity_id, "state": sensor.state},
        )
    return value


def plane_title(data: Mapping[str, Any]) -> str:
    """Build a plane subentry title from its declination/azimuth/power.

    A sensor-backed angle is labelled by its entity ID, not its friendly name:
    the title then only changes on a rename, which the integration follows.
    """
    declination = data.get(CONF_DECLINATION_SENSOR) or f"{data[CONF_DECLINATION]}°"
    azimuth = data.get(CONF_AZIMUTH_SENSOR) or f"{data[CONF_AZIMUTH]}°"
    return f"{declination} / {azimuth} / {data[CONF_MODULES_POWER]}W"
