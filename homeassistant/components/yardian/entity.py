"""Base entities for Yardian integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import YardianUpdateCoordinator


class YardianEntity(CoordinatorEntity[YardianUpdateCoordinator]):
    """Base class for Yardian entities assigned to the main device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: YardianUpdateCoordinator) -> None:
        """Initialize the main device entity."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info


class YardianZoneEntity(CoordinatorEntity[YardianUpdateCoordinator]):
    """Base class for Yardian entities assigned to a zone child device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: YardianUpdateCoordinator, zone_id: int) -> None:
        """Initialize the zone device entity."""
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.yid}_{zone_id}")},
            name=coordinator.data.zones[zone_id].name,
            manufacturer=MANUFACTURER,
            via_device=(DOMAIN, coordinator.yid),
        )
