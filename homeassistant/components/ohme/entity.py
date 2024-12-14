"""Base class for entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN


class OhmeEntity(CoordinatorEntity[DataUpdateCoordinator]):
    """Base class for all Ohme entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self.entity_description = entity_description

        client = coordinator.client
        self._attr_unique_id = f"{client.serial}_{entity_description.key}"

        device_info = client.device_info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, client.serial)},
            name=device_info["name"],
            manufacturer="Ohme",
            model=device_info["model"],
            sw_version=device_info["sw_version"],
            serial_number=client.serial,
        )

    @property
    def available(self) -> bool:
        """Return if charger reporting as online."""
        return super().available and self.coordinator.client.available
