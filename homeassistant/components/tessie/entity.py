"""Tessie parent entity class."""


from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODELS
from .coordinator import TessieDataUpdateCoordinator


class TessieEntity(CoordinatorEntity[TessieDataUpdateCoordinator]):
    """Parent class for Tessie Entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TessieDataUpdateCoordinator,
        key: str,
    ) -> None:
        """Initialize common aspects of a Tessie entity."""
        super().__init__(coordinator)
        self.vin = coordinator.vin
        self.key = key

        car_type = coordinator.data["vehicle_config-car_type"]

        self._attr_translation_key = key
        self._attr_unique_id = f"{self.vin}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.vin)},
            manufacturer="Tesla",
            configuration_url="https://my.tessie.com/",
            name=coordinator.data["display_name"],
            model=MODELS.get(car_type, car_type),
            sw_version=coordinator.data["vehicle_state-car_version"],
            hw_version=coordinator.data["vehicle_config-driver_assist"],
        )

    @property
    def value(self) -> Any:
        """Return value from coordinator data."""
        return self.coordinator.data[self.key]
