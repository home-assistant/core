"""Provides helpers for RFXtrx."""

from RFXtrx import RFXtrxDevice, get_device

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from . import get_device_tuple_from_identifiers


@callback
def async_get_device_object(hass: HomeAssistant, device_id: str) -> RFXtrxDevice:
    """Get a device for the given device registry id."""
    device_registry = dr.async_get(hass)
    registry_device = device_registry.async_get(device_id)
    if registry_device is None:
        raise ValueError(f"Device {device_id} not found")

    device_tuple = get_device_tuple_from_identifiers(registry_device.identifiers)
    assert device_tuple

    return get_device(
        int(device_tuple[0], 16), int(device_tuple[1], 16), device_tuple[2]
    )
