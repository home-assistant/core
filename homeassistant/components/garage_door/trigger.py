"""Provides triggers for garage doors."""

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN, CoverDeviceClass
from homeassistant.components.cover.trigger import (  # pylint: disable=hass-component-root-import
    CoverClosedTriggerBase,
    CoverOpenedTriggerBase,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import Trigger

DEVICE_CLASSES_GARAGE_DOOR: dict[str, str] = {
    BINARY_SENSOR_DOMAIN: BinarySensorDeviceClass.GARAGE_DOOR,
    COVER_DOMAIN: CoverDeviceClass.GARAGE,
}


class GarageDoorOpenedTrigger(CoverOpenedTriggerBase):
    """Trigger for garage door opened state changes."""

    _device_classes = DEVICE_CLASSES_GARAGE_DOOR


class GarageDoorClosedTrigger(CoverClosedTriggerBase):
    """Trigger for garage door closed state changes."""

    _device_classes = DEVICE_CLASSES_GARAGE_DOOR


TRIGGERS: dict[str, type[Trigger]] = {
    "opened": GarageDoorOpenedTrigger,
    "closed": GarageDoorClosedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for garage doors."""
    return TRIGGERS
