"""Provides triggers for garage doors."""

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

DEVICE_CLASSES_GARAGE_DOOR: dict[str, str] = {
    BINARY_SENSOR_DOMAIN: BinarySensorDeviceClass.GARAGE_DOOR,
    COVER_DOMAIN: CoverDeviceClass.GARAGE,
}


TRIGGERS: dict[str, type[Trigger]] = {
    "opened": make_cover_opened_trigger(device_classes=DEVICE_CLASSES_GARAGE_DOOR),
    "closed": make_cover_closed_trigger(device_classes=DEVICE_CLASSES_GARAGE_DOOR),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for garage doors."""
    return TRIGGERS
