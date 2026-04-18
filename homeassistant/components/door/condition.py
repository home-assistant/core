"""Provides conditions for doors."""

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    CoverDeviceClass,
    make_cover_is_closed_condition,
    make_cover_is_open_condition,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.condition import Condition

DEVICE_CLASSES_DOOR: dict[str, str] = {
    BINARY_SENSOR_DOMAIN: BinarySensorDeviceClass.DOOR,
    COVER_DOMAIN: CoverDeviceClass.DOOR,
}

CONDITIONS: dict[str, type[Condition]] = {
    "is_closed": make_cover_is_closed_condition(device_classes=DEVICE_CLASSES_DOOR),
    "is_open": make_cover_is_open_condition(device_classes=DEVICE_CLASSES_DOOR),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for doors."""
    return CONDITIONS
