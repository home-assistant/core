"""Provides helpers for RFXtrx."""


from RFXtrx import get_device


async def async_get_device_object(hass, device_id):
    """Get a device for the given device registry id."""
    device_registry = await hass.helpers.device_registry.async_get_registry()
    registry_device = device_registry.async_get(device_id)
    if registry_device is None:
        return None

    device_tuple = list(list(registry_device.identifiers)[0])
    try:
        return get_device(
            int(device_tuple[1], 16), int(device_tuple[2], 16), device_tuple[3]
        )
    except ValueError:
        return None
