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
from homeassistant.helpers.condition import (
    Condition,
    make_entity_numerical_condition,
    make_entity_state_condition,
)

CONDITIONS: dict[str, type[Condition]] = {
    "is_low": make_entity_state_condition(
        BINARY_SENSOR_DOMAIN,
        STATE_ON,
        device_classes={BINARY_SENSOR_DOMAIN: BinarySensorDeviceClass.BATTERY},
    ),
    "is_not_low": make_entity_state_condition(
        BINARY_SENSOR_DOMAIN,
        STATE_OFF,
        device_classes={BINARY_SENSOR_DOMAIN: BinarySensorDeviceClass.BATTERY},
    ),
    "is_charging": make_entity_state_condition(
        BINARY_SENSOR_DOMAIN,
        STATE_ON,
        device_classes={BINARY_SENSOR_DOMAIN: BinarySensorDeviceClass.BATTERY_CHARGING},
    ),
    "is_not_charging": make_entity_state_condition(
        BINARY_SENSOR_DOMAIN,
        STATE_OFF,
        device_classes={BINARY_SENSOR_DOMAIN: BinarySensorDeviceClass.BATTERY_CHARGING},
    ),
    "percentage": make_entity_numerical_condition(
        SENSOR_DOMAIN,
        device_classes={
            SENSOR_DOMAIN: SensorDeviceClass.BATTERY,
            NUMBER_DOMAIN: NumberDeviceClass.BATTERY,
        },
    ),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for batteries."""
    return CONDITIONS
