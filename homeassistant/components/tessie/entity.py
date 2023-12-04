"""Tessie parent entity class."""


from typing import Any

from aiohttp import ClientSession

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODELS, TessieCategory, TessieKey
from .coordinator import TessieDataUpdateCoordinator


class TessieEntity(CoordinatorEntity[TessieDataUpdateCoordinator]):
    """Parent class for Tessie Entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TessieDataUpdateCoordinator,
        vin: str,
        category: str,
        key: str,
    ) -> None:
        """Initialize common aspects of a Tessie entity."""
        super().__init__(coordinator)
        self.vin: str = vin
        self.category: str = category
        self.key: str = key
        self.session: ClientSession = coordinator.session

        car_data = coordinator.data[vin]
        car_type = car_data[TessieCategory.VEHICLE_CONFIG]["car_type"]

        self._attr_translation_key = key
        self._attr_unique_id = f"{vin}:{category}:{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vin)},
            manufacturer="Tesla",
            configuration_url="https://my.tessie.com/",
            name=car_data[TessieKey.DISPLAY_NAME],
            model=MODELS.get(car_type, car_type),
            sw_version=car_data[TessieCategory.VEHICLE_STATE]["car_version"],
            hw_version=car_data[TessieCategory.VEHICLE_CONFIG]["driver_assist"],
        )

    def get(self) -> Any:
        """Return value from coordinator data."""
        return self.coordinator.data[self.vin][self.category][self.key]
