"""Base entity for Tami4Edge."""
from __future__ import annotations

from Tami4EdgeAPI import Tami4EdgeAPI

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import DOMAIN


class Tami4EdgeBaseEntity(Entity):
    """Base class for Tami4Edge entities."""

    _attr_has_entity_name = True

    def __init__(
        self, api: Tami4EdgeAPI, entity_description: EntityDescription
    ) -> None:
        """Initialize the Tami4Edge."""
        self._state = None
        self._api = api
        device_id = api.device.psn
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}_{self.entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer="Stratuss",
            name=api.device.name,
            model="Tami4",
            sw_version=api.device.device_firmware,
            suggested_area="Kitchen",
        )
