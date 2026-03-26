"""Provides triggers for illuminance."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, NumberDeviceClass
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import LIGHT_LUX, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import (
    Trigger,
    make_entity_numerical_state_changed_trigger,
    make_entity_numerical_state_crossed_threshold_trigger,
    make_entity_target_state_trigger,
)

ILLUMINANCE_DOMAIN_SPECS: dict[str, DomainSpec] = {
    NUMBER_DOMAIN: DomainSpec(device_class=NumberDeviceClass.ILLUMINANCE),
    SENSOR_DOMAIN: DomainSpec(device_class=SensorDeviceClass.ILLUMINANCE),
}

TRIGGERS: dict[str, type[Trigger]] = {
    "detected": make_entity_target_state_trigger(
        {BINARY_SENSOR_DOMAIN: DomainSpec(device_class=BinarySensorDeviceClass.LIGHT)},
        STATE_ON,
    ),
    "cleared": make_entity_target_state_trigger(
        {BINARY_SENSOR_DOMAIN: DomainSpec(device_class=BinarySensorDeviceClass.LIGHT)},
        STATE_OFF,
    ),
    "changed": make_entity_numerical_state_changed_trigger(
        ILLUMINANCE_DOMAIN_SPECS, valid_unit=LIGHT_LUX
    ),
    "crossed_threshold": make_entity_numerical_state_crossed_threshold_trigger(
        ILLUMINANCE_DOMAIN_SPECS, valid_unit=LIGHT_LUX
    ),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for illuminance."""
    return TRIGGERS
