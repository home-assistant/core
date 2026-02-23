"""Provides triggers for binary sensors."""

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import get_device_class
from homeassistant.helpers.trigger import EntityTargetStateTriggerBase, Trigger
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from . import DOMAIN, BinarySensorDeviceClass


def get_device_class_or_undefined(
    hass: HomeAssistant, entity_id: str
) -> str | None | UndefinedType:
    """Get the device class of an entity or UNDEFINED if not found."""
    try:
        return get_device_class(hass, entity_id)
    except HomeAssistantError:
        return UNDEFINED


class BinarySensorOnOffTrigger(EntityTargetStateTriggerBase):
    """Class for binary sensor on/off triggers."""

    _device_class: BinarySensorDeviceClass | None
    _domain: str = DOMAIN

    def entity_filter(self, entities: set[str]) -> set[str]:
        """Filter entities of this domain."""
        entities = super().entity_filter(entities)
        return {
            entity_id
            for entity_id in entities
            if get_device_class_or_undefined(self._hass, entity_id)
            == self._device_class
        }


def make_binary_sensor_trigger(
    device_class: BinarySensorDeviceClass | None,
    to_state: str,
) -> type[BinarySensorOnOffTrigger]:
    """Create an entity state trigger class."""

    class CustomTrigger(BinarySensorOnOffTrigger):
        """Trigger for entity state changes."""

        _device_class = device_class
        _to_states = {to_state}

    return CustomTrigger


TRIGGERS: dict[str, type[Trigger]] = {
    "occupancy_detected": make_binary_sensor_trigger(
        BinarySensorDeviceClass.OCCUPANCY, STATE_ON
    ),
    "occupancy_cleared": make_binary_sensor_trigger(
        BinarySensorDeviceClass.OCCUPANCY, STATE_OFF
    ),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for binary sensors."""
    return TRIGGERS
