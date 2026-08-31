"""Provides conditions for moisture."""

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

MOISTURE_BINARY_DOMAIN_SPECS: dict[str, DomainSpec] = {
    BINARY_SENSOR_DOMAIN: DomainSpec(device_class=BinarySensorDeviceClass.MOISTURE),
}

MOISTURE_NUMERICAL_DOMAIN_SPECS: dict[str, DomainSpec] = {
    SENSOR_DOMAIN: DomainSpec(device_class=SensorDeviceClass.MOISTURE),
}

CONDITIONS: dict[str, type[Condition]] = {
    "is_detected": make_entity_state_condition(MOISTURE_BINARY_DOMAIN_SPECS, STATE_ON),
    "is_not_detected": make_entity_state_condition(
        MOISTURE_BINARY_DOMAIN_SPECS, STATE_OFF
    ),
    "is_value": make_entity_numerical_condition(
        MOISTURE_NUMERICAL_DOMAIN_SPECS, PERCENTAGE
    ),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for moisture."""
    return CONDITIONS
