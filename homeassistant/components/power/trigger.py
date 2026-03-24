"""Provides triggers for power."""

from __future__ import annotations

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, NumberDeviceClass
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import NumericalDomainSpec
from homeassistant.helpers.trigger import (
    Trigger,
    make_entity_numerical_state_changed_with_unit_trigger,
    make_entity_numerical_state_crossed_threshold_with_unit_trigger,
)
from homeassistant.util.unit_conversion import PowerConverter

POWER_DOMAIN_SPECS: dict[str, NumericalDomainSpec] = {
    NUMBER_DOMAIN: NumericalDomainSpec(device_class=NumberDeviceClass.POWER),
    SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.POWER),
}


TRIGGERS: dict[str, type[Trigger]] = {
    "changed": make_entity_numerical_state_changed_with_unit_trigger(
        POWER_DOMAIN_SPECS, UnitOfPower.WATT, PowerConverter
    ),
    "crossed_threshold": make_entity_numerical_state_crossed_threshold_with_unit_trigger(
        POWER_DOMAIN_SPECS, UnitOfPower.WATT, PowerConverter
    ),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for power."""
    return TRIGGERS
