"""Provides conditions for illuminance."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import LIGHT_LUX, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import (
    Condition,
    make_entity_numerical_condition,
    make_entity_state_condition,
)

ILLUMINANCE_DETECTED_DOMAIN_SPECS = {
    BINARY_SENSOR_DOMAIN: DomainSpec(device_class=BinarySensorDeviceClass.LIGHT)
}
ILLUMINANCE_VALUE_DOMAIN_SPECS = {
    SENSOR_DOMAIN: DomainSpec(device_class=SensorDeviceClass.ILLUMINANCE),
}

CONDITIONS: dict[str, type[Condition]] = {
    "is_detected": make_entity_state_condition(
        ILLUMINANCE_DETECTED_DOMAIN_SPECS, STATE_ON
    ),
    "is_not_detected": make_entity_state_condition(
        ILLUMINANCE_DETECTED_DOMAIN_SPECS, STATE_OFF
    ),
    "is_value": make_entity_numerical_condition(
        ILLUMINANCE_VALUE_DOMAIN_SPECS, LIGHT_LUX
    ),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for illuminance."""
    return CONDITIONS
