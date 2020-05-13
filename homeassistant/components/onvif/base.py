"""Base classes for ONVIF entities."""
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import Entity

from .device import ONVIFDevice
from .models import Profile


class ONVIFBaseEntity(Entity):
    """Base class common to all ONVIF entities."""

    def __init__(self, device: ONVIFDevice, profile: Profile = None) -> None:
        """Initialize the ONVIF entity."""
        self.device = device
        self.profile = profile

    @property
    def available(self):
        """Return True if device is available."""
        return self.device.available

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {
            "connections": {(CONNECTION_NETWORK_MAC, self.device.info.mac)},
            "manufacturer": self.device.info.manufacturer,
            "model": self.device.info.model,
            "name": self.device.name,
            "sw_version": self.device.info.fw_version,
        }
