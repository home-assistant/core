"""Provides triggers for moisture."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.automation import DomainSpec, NumericalDomainSpec
from homeassistant.helpers.trigger import (
    EntityNumericalStateChangedTriggerBase,
    EntityNumericalStateCrossedThresholdTriggerBase,
    EntityNumericalStateTriggerBase,
    EntityTriggerBase,
    Trigger,
)


class _MoistureBinaryTriggerBase(EntityTriggerBase):
    """Base trigger for moisture binary sensor state changes."""

    _target_state: str
    _domain_specs = {
        BINARY_SENSOR_DOMAIN: DomainSpec(device_class=BinarySensorDeviceClass.MOISTURE)
    }

    def is_valid_state(self, state: State) -> bool:
        """Check if the state matches the target moisture state."""
        return state.state == self._target_state

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the transition is valid for a moisture state change."""
        if from_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return False
        return from_state.state != to_state.state


class MoistureDetectedTrigger(_MoistureBinaryTriggerBase):
    """Trigger for moisture detected (binary sensor ON)."""

    _target_state = STATE_ON


class MoistureClearedTrigger(_MoistureBinaryTriggerBase):
    """Trigger for moisture cleared (binary sensor OFF)."""

    _target_state = STATE_OFF


class _MoistureNumericalTriggerMixin(EntityNumericalStateTriggerBase):
    """Mixin for moisture numerical triggers providing entity filtering and value extraction."""

    _domain_specs = {
        SENSOR_DOMAIN: NumericalDomainSpec(device_class=SensorDeviceClass.MOISTURE)
    }
    _valid_unit = "%"


class MoistureChangedTrigger(
    _MoistureNumericalTriggerMixin, EntityNumericalStateChangedTriggerBase
):
    """Trigger for moisture value changes."""


class MoistureCrossedThresholdTrigger(
    _MoistureNumericalTriggerMixin,
    EntityNumericalStateCrossedThresholdTriggerBase,
):
    """Trigger for moisture value crossing a threshold."""


TRIGGERS: dict[str, type[Trigger]] = {
    "detected": MoistureDetectedTrigger,
    "cleared": MoistureClearedTrigger,
    "changed": MoistureChangedTrigger,
    "crossed_threshold": MoistureCrossedThresholdTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for moisture."""
    return TRIGGERS
