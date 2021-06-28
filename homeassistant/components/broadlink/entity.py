"""Broadlink entities."""

from homeassistant.helpers import device_registry as dr

from .const import DOMAIN


class BroadlinkEntity:
    """Representation of a Broadlink entity."""

    _attr_should_poll = False

    def __init__(self, device):
        """Initialize the device."""
        self._device = device

    @property
    def available(self):
        """Return True if the remote is available."""
        return self._device.update_manager.available

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._device.unique_id)},
            "connections": {(dr.CONNECTION_NETWORK_MAC, self._device.mac_address)},
            "manufacturer": self._device.api.manufacturer,
            "model": self._device.api.model,
            "name": self._device.name,
            "sw_version": self._device.fw_version,
        }
