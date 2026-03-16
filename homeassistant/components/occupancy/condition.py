"""Provides conditions for occupancy."""

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import Condition, EntityStateConditionBase


class OccupancyIsDetectedCondition(EntityStateConditionBase):
    """Condition for occupancy detected (binary sensor ON)."""

    _domain_specs = {
        BINARY_SENSOR_DOMAIN: DomainSpec(device_class=BinarySensorDeviceClass.OCCUPANCY)
    }
    _states = {STATE_ON}


class OccupancyIsNotDetectedCondition(EntityStateConditionBase):
    """Condition for occupancy not detected (binary sensor OFF)."""

    _domain_specs = {
        BINARY_SENSOR_DOMAIN: DomainSpec(device_class=BinarySensorDeviceClass.OCCUPANCY)
    }
    _states = {STATE_OFF}


CONDITIONS: dict[str, type[Condition]] = {
    "is_detected": OccupancyIsDetectedCondition,
    "is_not_detected": OccupancyIsNotDetectedCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for occupancy."""
    return CONDITIONS
