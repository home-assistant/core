"""Provides conditions for batteries."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, NumberDeviceClass
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import (
    Condition,
    make_entity_numerical_condition,
    make_entity_state_condition,
)

CONDITIONS: dict[str, type[Condition]] = {
    "is_low": make_entity_state_condition(
        {
            BINARY_SENSOR_DOMAIN: DomainSpec(
                device_class=BinarySensorDeviceClass.BATTERY
            )
        },
        STATE_ON,
    ),
    "is_not_low": make_entity_state_condition(
        {
            BINARY_SENSOR_DOMAIN: DomainSpec(
                device_class=BinarySensorDeviceClass.BATTERY
            )
        },
        STATE_OFF,
    ),
    "is_charging": make_entity_state_condition(
        {
            BINARY_SENSOR_DOMAIN: DomainSpec(
                device_class=BinarySensorDeviceClass.BATTERY_CHARGING
            )
        },
        STATE_ON,
    ),
    "is_not_charging": make_entity_state_condition(
        {
            BINARY_SENSOR_DOMAIN: DomainSpec(
                device_class=BinarySensorDeviceClass.BATTERY_CHARGING
            )
        },
        STATE_OFF,
    ),
    "percentage": make_entity_numerical_condition(
        {
            SENSOR_DOMAIN: DomainSpec(device_class=SensorDeviceClass.BATTERY),
            NUMBER_DOMAIN: DomainSpec(device_class=NumberDeviceClass.BATTERY),
        },
    ),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for batteries."""
    return CONDITIONS
