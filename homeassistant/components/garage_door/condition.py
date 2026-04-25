"""Provides conditions for garage doors."""

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

DEVICE_CLASSES_GARAGE_DOOR: dict[str, str] = {
    BINARY_SENSOR_DOMAIN: BinarySensorDeviceClass.GARAGE_DOOR,
    COVER_DOMAIN: CoverDeviceClass.GARAGE,
}

CONDITIONS: dict[str, type[Condition]] = {
    "is_closed": make_cover_is_closed_condition(
        device_classes=DEVICE_CLASSES_GARAGE_DOOR
    ),
    "is_open": make_cover_is_open_condition(device_classes=DEVICE_CLASSES_GARAGE_DOOR),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for garage doors."""
    return CONDITIONS
