"""Provides triggers for power."""

from __future__ import annotations

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, NumberDeviceClass
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import NumericalDomainSpec
from homeassistant.helpers.trigger import (
    EntityNumericalStateChangedTriggerWithUnitBase,
    EntityNumericalStateCrossedThresholdTriggerWithUnitBase,
    EntityNumericalStateTriggerWithUnitBase,
    Trigger,
)
from homeassistant.util.unit_conversion import PowerConverter

POWER_DOMAIN_SPECS: dict[str, NumericalDomainSpec] = {
    NUMBER_DOMAIN: NumericalDomainSpec(device_class=NumberDeviceClass.POWER),
    SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.POWER),
}


class _PowerTriggerMixin(EntityNumericalStateTriggerWithUnitBase):
    """Mixin for power triggers providing entity filtering, value extraction, and unit conversion."""

    _base_unit = UnitOfPower.WATT
    _domain_specs = POWER_DOMAIN_SPECS
    _unit_converter = PowerConverter


class PowerChangedTrigger(
    _PowerTriggerMixin, EntityNumericalStateChangedTriggerWithUnitBase
):
    """Trigger for power value changes."""


class PowerCrossedThresholdTrigger(
    _PowerTriggerMixin, EntityNumericalStateCrossedThresholdTriggerWithUnitBase
):
    """Trigger for power value crossing a threshold."""


TRIGGERS: dict[str, type[Trigger]] = {
    "changed": PowerChangedTrigger,
    "crossed_threshold": PowerCrossedThresholdTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for power."""
    return TRIGGERS
