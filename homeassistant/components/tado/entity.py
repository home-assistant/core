"""Base class for August entity."""

import logging

from homeassistant.helpers.entity import Entity

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


class TadoZoneEntity(Entity):
    """Base implementation for tado device."""

    def __init__(self, zone_name, device_info, device_id, zone_id):
        """Initialize an August device."""
        super().__init__()
        self._device_zone_id = f"{device_id}_{zone_id}"
        self._device_info = device_info
        self.zone_name = zone_name

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self._device_zone_id)},
            "name": self.zone_name,
            "manufacturer": DEFAULT_NAME,
            "sw_version": self._device_info["currentFwVersion"],
            "model": self._device_info["deviceType"],
            "via_device": (DOMAIN, self._device_info["serialNo"]),
        }

    @property
    def should_poll(self):
        """Do not poll."""
        return False
