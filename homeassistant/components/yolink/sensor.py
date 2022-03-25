"""Support for Yolink Devices."""

from homeassistant.components.yolink.device_impl import YoLinkDoorSensor

from .const import DOMAIN, HOME_SUBSCRIPTION
from .device import YoLinkDevice


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Perform the setup for YoLink devices."""
    devices = []
    entities: list[YoLinkDevice] = []
    for device in hass.data[DOMAIN][config_entry.entry_id]["devices"]:
        if device["type"] == "DoorSensor":
            devices.append(YoLinkDoorSensor(device, hass, config_entry))

    for device in devices:
        entities.extend(device.entities)

    hass.data[DOMAIN][config_entry.entry_id][HOME_SUBSCRIPTION].attachPlatformDevices(
        "sensor", devices
    )
    async_add_entities(entities)
