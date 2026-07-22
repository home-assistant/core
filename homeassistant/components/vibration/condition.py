"""Provides conditions for vibration."""

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import Condition, make_entity_state_condition

VIBRATION_DOMAIN_SPECS: dict[str, DomainSpec] = {
    BINARY_SENSOR_DOMAIN: DomainSpec(device_class=BinarySensorDeviceClass.VIBRATION),
}


CONDITIONS: dict[str, type[Condition]] = {
    "is_detected": make_entity_state_condition(VIBRATION_DOMAIN_SPECS, STATE_ON),
    "is_not_detected": make_entity_state_condition(VIBRATION_DOMAIN_SPECS, STATE_OFF),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for vibration."""
    return CONDITIONS
