"""The Tesla Powerwall integration base entity."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MANUFACTURER,
    POWERWALL_API,
    POWERWALL_BASE_INFO,
    POWERWALL_COORDINATOR,
)
from .coordinator import PowerwallData, PowerwallRuntimeData, PowerwallUpdateCoordinator


class PowerWallEntity(CoordinatorEntity[PowerwallUpdateCoordinator]):
    """Base class for powerwall entities."""

    _attr_has_entity_name = True

    def __init__(self, powerwall_data: PowerwallRuntimeData) -> None:
        """Initialize the entity."""
        base_info = powerwall_data[POWERWALL_BASE_INFO]
        coordinator = powerwall_data[POWERWALL_COORDINATOR]
        assert coordinator is not None
        super().__init__(coordinator)
        self.power_wall = powerwall_data[POWERWALL_API]
        self.base_unique_id = base_info.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.base_unique_id)},
            manufacturer=MANUFACTURER,
            model=base_info.device_type,
            name=base_info.site_name or base_info.device_type,
            sw_version=base_info.version,
            configuration_url=base_info.url,
        )

    @property
    def data(self) -> PowerwallData:
        """Return the coordinator data."""
        return self.coordinator.data
