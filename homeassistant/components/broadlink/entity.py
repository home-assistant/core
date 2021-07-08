"""Broadlink entities."""

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class BroadlinkEntity(Entity):
    """Representation of a Broadlink entity."""

    _attr_should_poll = False

    def __init__(self, device):
        """Initialize the device."""
        self._device = device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.unique_id)},
            "connections": {(dr.CONNECTION_NETWORK_MAC, device.mac_address)},
            "manufacturer": device.api.manufacturer,
            "model": device.api.model,
            "name": device.name,
            "sw_version": device.fw_version,
        }

    @property
    def available(self):
        """Return True if the remote is available."""
        return self._device.update_manager.available
