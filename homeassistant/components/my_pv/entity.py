"""Base entity for the my-PV integration."""

from typing import override

from my_pv.exceptions import MyPVNotSupportedError

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
        super().__init__(coordinator, entity_description.key)

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{serial_number}-{entity_description.key}"

        self.entity_description = entity_description

    @override
    async def async_added_to_hass(self) -> None:
        """Call when entity is added to Home Assistant."""
        await super().async_added_to_hass()

        self._handle_coordinator_update()

    @override
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.connected or self.coordinator.device.is_on is None:
            return False
        try:
            if self.coordinator.get_data_value(self.entity_description.key) is None:
                return False
        except MyPVNotSupportedError:
            return False

        return super().available
