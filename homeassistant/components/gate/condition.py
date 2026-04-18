"""Provides conditions for gates."""

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    CoverDeviceClass,
    make_cover_is_closed_condition,
    make_cover_is_open_condition,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.condition import Condition

DEVICE_CLASSES_GATE: dict[str, str] = {
    COVER_DOMAIN: CoverDeviceClass.GATE,
}

CONDITIONS: dict[str, type[Condition]] = {
    "is_closed": make_cover_is_closed_condition(device_classes=DEVICE_CLASSES_GATE),
    "is_open": make_cover_is_open_condition(device_classes=DEVICE_CLASSES_GATE),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for gates."""
    return CONDITIONS
