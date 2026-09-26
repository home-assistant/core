"""Base entity for PowerShades."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import PowerShadesCoordinator


class PowerShadesEntity(CoordinatorEntity[PowerShadesCoordinator]):
    """Base entity for PowerShades devices."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PowerShadesCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_{key}"
        self._attr_device_info = coordinator.device_info
