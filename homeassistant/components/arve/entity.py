"""Arve base entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ArveCoordinator


class ArveDeviceEntity(CoordinatorEntity[ArveCoordinator]):
    """Defines a base Arve device entity."""

    _attr_has_entity_name = True
    _attr_available = True

    def __init__(
        self, coordinator: ArveCoordinator, description: EntityDescription
    ) -> None:
        """Initialize the Arve device entity."""
        super().__init__(coordinator)

        self._entry = coordinator.config_entry
        self.arve = coordinator.arve
        self.coordinator = coordinator

        self.entity_description = description
        self.trans_key = str(self.entity_description.translation_key)
        self.sn = coordinator.arve.device_sn
        self._attr_unique_id = "_".join(
            [
                self.sn,
                self.trans_key,
            ]
        )

        self.name = description.key

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.sn)},
            manufacturer="Calanda Air AG",
            model="Arve Sens Pro",
            sw_version="1.0.0",
        )
