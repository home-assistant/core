"""Tessie parent entity class."""


from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class TessieEntity(CoordinatorEntity):
    """Parent class for Advantage Air Entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, vin: str, category: str, name: str) -> None:
        """Initialize common aspects of an Advantage Air entity."""
        super().__init__(coordinator)
        self.vin = vin
        self.category = category
        self._attr_unique_id = f"{vin}:{category}:{name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vin)},
            manufacturer="Tesla",
            configuration_url="https://my.tessie.com/",
            name=coordinator.data[vin]["display_name"],
            model=coordinator.data[vin]["vehicle_config"]["car_type"],
        )
