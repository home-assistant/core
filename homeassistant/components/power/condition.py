"""Provides conditions for power."""

from __future__ import annotations

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, NumberDeviceClass
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import (
    Condition,
    make_entity_numerical_condition_with_unit,
)
from homeassistant.util.unit_conversion import PowerConverter

POWER_DOMAIN_SPECS = {
    NUMBER_DOMAIN: DomainSpec(device_class=NumberDeviceClass.POWER),
    SENSOR_DOMAIN: DomainSpec(device_class=SensorDeviceClass.POWER),
}


CONDITIONS: dict[str, type[Condition]] = {
    "is_value": make_entity_numerical_condition_with_unit(
        POWER_DOMAIN_SPECS, UnitOfPower.WATT, PowerConverter
    ),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the power conditions."""
    return CONDITIONS
