"""Provides conditions for moisture."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import PERCENTAGE, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import (
    Condition,
    make_entity_numerical_condition,
    make_entity_state_condition,
)

_MOISTURE_BINARY_DOMAIN_SPECS = {
    BINARY_SENSOR_DOMAIN: DomainSpec(
        device_class=BinarySensorDeviceClass.MOISTURE,
    )
}

_MOISTURE_NUMERICAL_DOMAIN_SPECS = {
    SENSOR_DOMAIN: DomainSpec(device_class=SensorDeviceClass.MOISTURE),
}

CONDITIONS: dict[str, type[Condition]] = {
    "is_detected": make_entity_state_condition(_MOISTURE_BINARY_DOMAIN_SPECS, STATE_ON),
    "is_not_detected": make_entity_state_condition(
        _MOISTURE_BINARY_DOMAIN_SPECS, STATE_OFF
    ),
    "is_value": make_entity_numerical_condition(
        _MOISTURE_NUMERICAL_DOMAIN_SPECS, PERCENTAGE
    ),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for moisture."""
    return CONDITIONS
