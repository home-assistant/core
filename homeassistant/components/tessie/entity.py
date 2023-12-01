"""Tessie parent entity class."""


from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODELS, TessieApi
from .coordinator import TessieDataUpdateCoordinator


class TessieEntity(CoordinatorEntity[TessieDataUpdateCoordinator]):
    """Parent class for Tessie Entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        api_key: str,
        coordinator: TessieDataUpdateCoordinator,
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
        car_data = coordinator.data[vin]
        car_type = car_data[TessieApi.VEHICLE_CONFIG]["car_type"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vin)},
            manufacturer="Tessie",
            configuration_url="https://my.tessie.com/",
            name=car_data[TessieApi.DISPLAY_NAME],
            model=MODELS.get(car_type, car_type),
        )

    def get(self) -> Any:
        """Return value from coordinator data."""
        return self.coordinator.data[self.vin][self.category].get(self.key)
