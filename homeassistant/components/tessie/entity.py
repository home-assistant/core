"""Tessie parent entity class."""


from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, MODELS, TessieApi


class TessieEntity(CoordinatorEntity):
    """Parent class for Tessie Entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        api_key: str,
        coordinator: DataUpdateCoordinator,
        vin: str,
        category: str,
        key: str,
    ) -> None:
        """Initialize common aspects of a Tessie entity."""
        super().__init__(coordinator)
        self.api_key = api_key
        self.vin = vin
        self.category = category
        self.key = key
        self._attr_unique_id = f"{vin}:{category}:{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vin)},
            manufacturer="Tessie",
            configuration_url="https://my.tessie.com/",
            name=coordinator.data[vin][TessieApi.DISPLAY_NAME],
            model=MODELS.get(
                coordinator.data[vin][TessieApi.VEHICLE_CONFIG]["car_type"],
                coordinator.data[vin][TessieApi.VEHICLE_CONFIG]["car_type"],
            ),
        )

    def get(self) -> Any:
        """Return value from coordinator data."""
        return self.coordinator.data[self.vin][self.category].get(self.key)
