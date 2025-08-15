"""Base entity for the Snoo integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_BABY_MODEL, DEVICE_MANUFACTURER, DOMAIN
from .coordinator import SnooBabyCoordinator, SnooCoordinator


class SnooDescriptionEntity(CoordinatorEntity[SnooCoordinator]):
    """Defines an Snoo entity that uses a description."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: SnooCoordinator, description: EntityDescription
    ) -> None:
        """Initialize the Snoo entity."""
        super().__init__(coordinator)
        self.device = coordinator.device
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_unique_id)},
            name=self.device.name,
            manufacturer=DEVICE_MANUFACTURER,
            model="Snoo",
            serial_number=self.device.serialNumber,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data is not None and super().available


class SnooBabyDescriptionEntity(CoordinatorEntity[SnooBabyCoordinator]):
    """Defines a Snoo baby entity that uses a description."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: SnooBabyCoordinator, description: EntityDescription
    ) -> None:
        """Initialize the Snoo baby entity."""
        super().__init__(coordinator)
        self.baby = coordinator.baby
        self.entity_description = description
        self._attr_unique_id = f"snoo_baby_{coordinator.baby.baby_id}_{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.baby.baby_id)},
            name=coordinator.data.babyName,
            manufacturer=DEVICE_MANUFACTURER,
            model=DEVICE_BABY_MODEL,
            serial_number=coordinator.baby.baby_id,
            via_device=(DOMAIN, coordinator.snoo_unique_id),
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data is not None and super().available
