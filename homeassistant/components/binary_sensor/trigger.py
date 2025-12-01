"""Provides triggers for lights."""

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import get_device_class
from homeassistant.helpers.trigger import EntityStateTriggerBase, Trigger
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


class BinarySensorOnOffTrigger(EntityStateTriggerBase):
    """Class for cover opened and closed triggers."""

    _device_class: BinarySensorDeviceClass | None
    _domain: str = DOMAIN


def make_binary_sensor_trigger(
    device_class: BinarySensorDeviceClass | None,
    to_state: str,
) -> type[BinarySensorOnOffTrigger]:
    """Create an entity state trigger class."""

    class CustomTrigger(BinarySensorOnOffTrigger):
        """Trigger for entity state changes."""

        _device_class = device_class
        _to_state = to_state

    return CustomTrigger


TRIGGERS: dict[str, type[Trigger]] = {
    "started_detecting_presence": make_binary_sensor_trigger(
        BinarySensorDeviceClass.PRESENCE, STATE_ON
    ),
    "stopped_detecting_presence": make_binary_sensor_trigger(
        BinarySensorDeviceClass.PRESENCE, STATE_OFF
    ),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for lights."""
    return TRIGGERS
