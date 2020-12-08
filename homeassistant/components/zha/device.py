"""Device extensions for Zigbee Home Automation devices."""

from zigpy.types.named import EUI64

from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE

from .core.const import DATA_ZHA, DATA_ZHA_GATEWAY


async def async_get_device_info(hass, device_id):
    """Get ZHA device info."""
    device_info = None
    device_registry = await hass.helpers.device_registry.async_get_registry()
    zha_gateway = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY]
    device = device_registry.async_get(device_id)
    ieee = next(x[1] for x in device.connections if x[0] == CONNECTION_ZIGBEE)
    ieee = EUI64.convert(ieee)

    if ieee in zha_gateway.devices:
        device_info = zha_gateway.devices[ieee].zha_device_info

    return device_info
