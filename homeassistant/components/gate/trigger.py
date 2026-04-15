"""Provides triggers for gates."""

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    CoverDeviceClass,
    make_cover_closed_trigger,
    make_cover_opened_trigger,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import Trigger

DEVICE_CLASSES_GATE: dict[str, str] = {
    COVER_DOMAIN: CoverDeviceClass.GATE,
}


TRIGGERS: dict[str, type[Trigger]] = {
    "opened": make_cover_opened_trigger(device_classes=DEVICE_CLASSES_GATE),
    "closed": make_cover_closed_trigger(device_classes=DEVICE_CLASSES_GATE),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for gates."""
    return TRIGGERS
