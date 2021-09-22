"""Provides helpers for RFXtrx."""


from RFXtrx import get_device

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import HomeAssistantType


@callback
def async_get_device_object(hass: HomeAssistantType, device_id):
    """Get a device for the given device registry id."""
    device_registry = dr.async_get(hass)
    registry_device = device_registry.async_get(device_id)
    if registry_device is None:
        raise ValueError(f"Device {device_id} not found")

    device_tuple = list(list(registry_device.identifiers)[0])
    return get_device(
        int(device_tuple[1], 16), int(device_tuple[2], 16), device_tuple[3]
    )
