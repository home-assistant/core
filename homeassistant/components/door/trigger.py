"""Provides triggers for doors."""

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    CoverClosedTriggerBase,
    CoverDeviceClass,
    CoverOpenedTriggerBase,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import Trigger

DEVICE_CLASSES_DOOR: dict[str, str] = {
    BINARY_SENSOR_DOMAIN: BinarySensorDeviceClass.DOOR,
    COVER_DOMAIN: CoverDeviceClass.DOOR,
}


class DoorOpenedTrigger(CoverOpenedTriggerBase):
    """Trigger for door opened state changes."""

    _device_classes = DEVICE_CLASSES_DOOR


class DoorClosedTrigger(CoverClosedTriggerBase):
    """Trigger for door closed state changes."""

    _device_classes = DEVICE_CLASSES_DOOR


TRIGGERS: dict[str, type[Trigger]] = {
    "opened": DoorOpenedTrigger,
    "closed": DoorClosedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for doors."""
    return TRIGGERS
