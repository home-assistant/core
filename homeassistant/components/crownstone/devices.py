"""Base classes for Crownstone devices."""
from __future__ import annotations

from crownstone_cloud.cloud_models.crownstones import Crownstone

from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
)
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import CROWNSTONE_INCLUDE_TYPES, DOMAIN


class CrownstoneBaseEntity(Entity):
    """Base entity class for Crownstone devices."""

    _attr_should_poll = False

    def __init__(self, device: Crownstone) -> None:
        """Initialize the device."""
        self.device = device

    @property
    def cloud_id(self) -> str:
        """
        Return the unique identifier for this device.

        Used as device ID and to generate unique entity ID's.
        """
        return str(self.device.cloud_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self.cloud_id)},
            ATTR_NAME: self.device.name,
            ATTR_MANUFACTURER: "Crownstone",
            ATTR_MODEL: CROWNSTONE_INCLUDE_TYPES[self.device.type],
            ATTR_SW_VERSION: self.device.sw_version,
        }
