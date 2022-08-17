"""Base entity for Tami4Edge."""
from __future__ import annotations

from Tami4EdgeAPI import Tami4EdgeAPI

from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription

from .const import DOMAIN


class Tami4EdgeBaseEntity(Entity):
    """Base class for Tami4Edge entities."""

    def __init__(
        self, edge: Tami4EdgeAPI, entity_description: EntityDescription
    ) -> None:
        """Initialize the Tami4Edge."""
        self._state = None
        self._edge = edge
        self._name = f"{edge.device.name}"
        self._device_id = edge.device.psn
        self.entity_description = entity_description
        self._attr_unique_id = f"{self._device_id}_{self.entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, edge.device.psn)},
            manufacturer="Stratuss",
            name=edge.device.name,
            model="Tami4",
            sw_version=edge.device.device_firmware,
            suggested_area="Kitchen",
        )
