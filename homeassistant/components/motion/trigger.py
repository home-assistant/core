"""Provides triggers for motion."""

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import (
    EntityTargetStateTriggerBase,
    EntityTriggerBase,
    Trigger,
    get_device_class_or_undefined,
)


class _MotionBinaryTriggerBase(EntityTriggerBase):
    """Base trigger for motion binary sensor state changes."""

    _domains = {BINARY_SENSOR_DOMAIN}

    def entity_filter(self, entities: set[str]) -> set[str]:
        """Filter entities by motion device class."""
        entities = super().entity_filter(entities)
        return {
            entity_id
            for entity_id in entities
            if get_device_class_or_undefined(self._hass, entity_id)
            == BinarySensorDeviceClass.MOTION
        }


class MotionDetectedTrigger(_MotionBinaryTriggerBase, EntityTargetStateTriggerBase):
    """Trigger for motion detected (binary sensor ON)."""

    _to_states = {STATE_ON}


class MotionClearedTrigger(_MotionBinaryTriggerBase, EntityTargetStateTriggerBase):
    """Trigger for motion cleared (binary sensor OFF)."""

    _to_states = {STATE_OFF}


TRIGGERS: dict[str, type[Trigger]] = {
    "detected": MotionDetectedTrigger,
    "cleared": MotionClearedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for motion."""
    return TRIGGERS
