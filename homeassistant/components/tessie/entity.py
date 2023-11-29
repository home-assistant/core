"""Tessie parent entity class."""


from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

MODELS = {
    "model3": "Model 3",
    "modelx": "Model X",
    "modely": "Model Y",
    "models": "Model S",
}


class TessieEntity(CoordinatorEntity):
    """Parent class for Tessie Entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, vin: str, category: str, name: str) -> None:
        """Initialize common aspects of an Tessie entity."""
        super().__init__(coordinator)
        self.vin = vin
        self.category = category
        self._attr_unique_id = f"{vin}:{category}:{name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vin)},
            manufacturer="Tessie",
            configuration_url="https://my.tessie.com/",
            name=coordinator.data[vin]["display_name"],
            model=MODELS.get(
                coordinator.data[vin]["vehicle_config"]["car_type"],
                coordinator.data[vin]["vehicle_config"]["car_type"],
            ),
        )

    def get(self, key: str) -> Any:
        """Return value from coordinator data."""
        return self.coordinator.data[self.vin][self.category].get(key)
