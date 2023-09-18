"""Base classes for Crownstone devices."""
from __future__ import annotations

from crownstone_cloud.cloud_models.crownstones import Crownstone

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import CROWNSTONE_INCLUDE_TYPES, DOMAIN


class CrownstoneBaseEntity(Entity):
    """Base entity class for Crownstone devices."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, device: Crownstone) -> None:
        """Initialize the device."""
        self.device = device

    @property
    def cloud_id(self) -> str:
        """Return the unique identifier for this device.

        Used as device ID and to generate unique entity ID's.
        """
        return str(self.device.cloud_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.cloud_id)},
            manufacturer="Crownstone",
            model=CROWNSTONE_INCLUDE_TYPES[self.device.type],
            name=self.device.name,
            sw_version=self.device.sw_version,
        )
