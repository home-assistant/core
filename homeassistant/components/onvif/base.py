"""Base classes for ONVIF entities."""
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .device import ONVIFDevice
from .models import Profile


class ONVIFBaseEntity(Entity):
    """Base class common to all ONVIF entities."""

    def __init__(self, device: ONVIFDevice, profile: Profile = None) -> None:
        """Initialize the ONVIF entity."""
        self.device: ONVIFDevice = device
        self.profile: Profile = profile

    @property
    def available(self):
        """Return True if device is available."""
        return self.device.available

    @property
    def device_info(self):
        """Return a device description for device registry."""
        device_info = {
            "identifiers": {(DOMAIN, self.device.info.serial_number)},
            "manufacturer": self.device.info.manufacturer,
            "model": self.device.info.model,
            "name": self.device.name,
            "sw_version": self.device.info.fw_version,
        }

        if self.device.info.mac:
            device_info["connections"] = {
                (CONNECTION_NETWORK_MAC, self.device.info.mac)
            }

        return device_info
