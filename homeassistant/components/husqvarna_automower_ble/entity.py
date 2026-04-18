"""Provides the HusqvarnaAutomowerBleEntity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import HusqvarnaCoordinator


class HusqvarnaAutomowerBleEntity(CoordinatorEntity[HusqvarnaCoordinator]):
    """HusqvarnaCoordinator entity for Husqvarna Automower Bluetooth."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HusqvarnaCoordinator) -> None:
        """Initialize coordinator entity."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.address}_{coordinator.channel_id}")},
            manufacturer=MANUFACTURER,
            model_id=coordinator.model,
            suggested_area="Garden",
            connections={(CONNECTION_BLUETOOTH, format_mac(coordinator.address))},
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.mower.is_connected()


class HusqvarnaAutomowerBleDescriptorEntity(HusqvarnaAutomowerBleEntity):
    """Coordinator entity for entities with entity description."""

    def __init__(
        self, coordinator: HusqvarnaCoordinator, description: EntityDescription
    ) -> None:
        """Initialize description entity."""
        super().__init__(coordinator)

        self._attr_unique_id = (
            f"{coordinator.address}_{coordinator.channel_id}_{description.key}"
        )
        self.entity_description = description
