"""Provide a way to connect entities belonging to one device.
"""

import logging
import uuid

import attr

from homeassistant.core import callback
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)

DATA_REGISTRY = 'device_registry'


@attr.s(slots=True, frozen=True)
class DeviceEntry:
    """Device Registry Entry."""

    serial = attr.ib(type=str)
    manufacturer = attr.ib(type=str)
    model = attr.ib(type=str)
    connection = attr.ib(type=tuple)
    sw_version = attr.ib(type=str, default=None)
    id = attr.ib(type=str, default=attr.Factory(lambda: uuid.uuid4().hex))


class DeviceRegistry:
    """Class to hold a registry of devices."""

    def __init__(self, hass):
        """Initialize the device registry."""
        self.hass = hass
        self.devices = {}

    @callback
    def async_get_device(self, serial: str, connection: tuple):
        """Check if device is registered."""
        for device in self.devices.values():
            if (device.serial == serial or
                    device.connection == connection):
                return device
        return None

    @callback
    def async_get_or_create(self, serial, manufacturer, model,
                            connection, *, sw_version=None):
        """Get device. Create if it doesn't exist"""
        device = self.async_get_device(serial, connection)
        if device is None:
            device = DeviceEntry(
                serial=serial,
                manufacturer=manufacturer,
                model=model,
                connection=connection,
                sw_version=sw_version
            )
            self.devices[device.id] = device
        return device


@bind_hass
@callback
def async_get_registry(hass) -> DeviceRegistry:
    """Return device registry instance."""
    registry = hass.data.get(DATA_REGISTRY)

    if registry is None:
        registry = hass.data[DATA_REGISTRY] = DeviceRegistry(hass)

    return registry
