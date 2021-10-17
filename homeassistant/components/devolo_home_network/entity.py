"""Generic platform."""
from __future__ import annotations

import logging

from devolo_plc_api.device import Device

from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DevoloEntity(Entity):
    """Representation of a devolo home network device."""

    def __init__(self, device: Device, device_name: str) -> None:
        """Initialize a devolo home network device."""
        self._device = device
        self._device_name = device_name

        self._attr_state = 0
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._device.serial_number)},
            "manufacturer": "devolo",
            "model": self._device.product,
            "name": self._device_name,
            "sw_version": self._device.firmware_version,
        }

    def _set_availability(self, available: bool) -> None:
        """Set availability and log if changed."""
        if self.available and not available:
            _LOGGER.warning("Unable to connect to %s", self._device_name)
        if not self.available and available:
            _LOGGER.warning("Reconnected to %s", self._device_name)
        self._attr_available = available
