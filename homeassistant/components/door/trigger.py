"""Provides triggers for doors."""

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    CoverDeviceClass,
    make_cover_closed_trigger,
    make_cover_opened_trigger,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import Trigger

DEVICE_CLASSES_DOOR: dict[str, str] = {
    BINARY_SENSOR_DOMAIN: BinarySensorDeviceClass.DOOR,
    COVER_DOMAIN: CoverDeviceClass.DOOR,
}


TRIGGERS: dict[str, type[Trigger]] = {
    "opened": make_cover_opened_trigger(device_classes=DEVICE_CLASSES_DOOR),
    "closed": make_cover_closed_trigger(device_classes=DEVICE_CLASSES_DOOR),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for doors."""
    return TRIGGERS
