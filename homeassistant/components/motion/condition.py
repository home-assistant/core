"""Provides conditions for motion."""

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import Condition, EntityStateConditionBase


class MotionIsDetectedCondition(EntityStateConditionBase):
    """Condition for motion detected (binary sensor ON)."""

    _domain_specs = {
        BINARY_SENSOR_DOMAIN: DomainSpec(device_class=BinarySensorDeviceClass.MOTION)
    }
    _states = {STATE_ON}


class MotionIsNotDetectedCondition(EntityStateConditionBase):
    """Condition for motion not detected (binary sensor OFF)."""

    _domain_specs = {
        BINARY_SENSOR_DOMAIN: DomainSpec(device_class=BinarySensorDeviceClass.MOTION)
    }
    _states = {STATE_OFF}


CONDITIONS: dict[str, type[Condition]] = {
    "is_detected": MotionIsDetectedCondition,
    "is_not_detected": MotionIsNotDetectedCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for motion."""
    return CONDITIONS
