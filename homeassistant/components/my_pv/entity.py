"""Base entity for the my-PV integration."""

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MyPVCoordinator


class MyPVBaseEntity(CoordinatorEntity[MyPVCoordinator]):
    """The my-PV base entity."""

    _attr_has_entity_name = True
    _attr_available = False

    def __init__(
        self,
        coordinator: MyPVCoordinator,
        entity_description: EntityDescription,
        serial_number: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, entity_description.key)

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{serial_number}-{entity_description.key}"

        self.entity_description = entity_description


class MyPVDataEntity(MyPVBaseEntity):
    """The my-PV data entity."""

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.connected:
            return False
        if self.coordinator.device.is_on is None:
            return False
        if self.coordinator.get_data_value(self.entity_description.key) is None:
            return False

        return self.coordinator.last_update_success
