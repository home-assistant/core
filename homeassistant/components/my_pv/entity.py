"""Base entity for the my-PV integration."""

from typing import override

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MyPVCoordinator


class MyPVDataEntity(CoordinatorEntity[MyPVCoordinator]):
    """The my-PV data entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MyPVCoordinator,
        entity_description: EntityDescription,
        serial_number: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{serial_number}-{entity_description.key}"

        self.entity_description = entity_description

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.device.connected
            and self.coordinator.device.is_on is not None
            and self.coordinator.device.get_data_value(self.entity_description.key)
            is not None
        )
