"""Base entity for the my-PV integration."""

from typing import Any, override

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MyPVCoordinator


class MyPVBaseEntity(CoordinatorEntity[MyPVCoordinator]):
    """The my-PV base entity."""

    _attr_has_entity_name = True

    _configuration: dict[str, Any]

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
        self._configuration = (
            coordinator.device.get_setup_configuration(self.entity_description.key)
            or {}
        )

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.device.connected
            and self.coordinator.device.is_on is not None
        )


class MyPVDataEntity(MyPVBaseEntity):
    """The my-PV data entity."""

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.device.get_data_value(self.entity_description.key)
            is not None
        )


class MyPVSetupEntity(MyPVBaseEntity):
    """The my-PV data entity."""

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.device.get_setup_value(self.entity_description.key)
            is not None
        )
