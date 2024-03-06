"""Various utilities for the Bang & Olufsen integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN


def get_device(hass: HomeAssistant | None, unique_id: str) -> DeviceEntry | None:
    """Get the device."""
    if not isinstance(hass, HomeAssistant):
        return None

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, unique_id)})
    assert device

    return device
