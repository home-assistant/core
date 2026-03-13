"""Provides triggers for motion."""

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import (
    EntityTargetTriggerBase,
    EntityTriggerBase,
    Trigger,
)


class _MotionBinaryTriggerBase(EntityTriggerBase):
    """Base trigger for motion binary sensor state changes."""

    _domain_specs = {
        BINARY_SENSOR_DOMAIN: DomainSpec(device_class=BinarySensorDeviceClass.MOTION)
    }


class MotionDetectedTrigger(_MotionBinaryTriggerBase, EntityTargetTriggerBase):
    """Trigger for motion detected (binary sensor ON)."""

    _to_states = {STATE_ON}


class MotionClearedTrigger(_MotionBinaryTriggerBase, EntityTargetTriggerBase):
    """Trigger for motion cleared (binary sensor OFF)."""

    _to_states = {STATE_OFF}


TRIGGERS: dict[str, type[Trigger]] = {
    "detected": MotionDetectedTrigger,
    "cleared": MotionClearedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for motion."""
    return TRIGGERS
