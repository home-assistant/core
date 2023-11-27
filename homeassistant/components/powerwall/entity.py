"""The Tesla Powerwall integration base entity."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    DOMAIN,
    MANUFACTURER,
    MODEL,
    POWERWALL_API,
    POWERWALL_BASE_INFO,
    POWERWALL_COORDINATOR,
)
from .models import PowerwallData, PowerwallRuntimeData


class PowerWallEntity(CoordinatorEntity[DataUpdateCoordinator[PowerwallData]]):
    """Base class for powerwall entities."""

    _attr_has_entity_name = True

    def __init__(self, powerwall_data: PowerwallRuntimeData) -> None:
        """Initialize the entity."""
        base_info = powerwall_data[POWERWALL_BASE_INFO]
        coordinator = powerwall_data[POWERWALL_COORDINATOR]
        assert coordinator is not None
        super().__init__(coordinator)
        self.power_wall = powerwall_data[POWERWALL_API]
        # The serial numbers of the powerwalls are unique to every site
        self.base_unique_id = "_".join(base_info.serial_numbers)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.base_unique_id)},
            manufacturer=MANUFACTURER,
            model=f"{MODEL} ({base_info.device_type.name})",
            name=base_info.site_info.site_name,
            sw_version=base_info.status.version,
            configuration_url=base_info.url,
        )

    @property
    def data(self) -> PowerwallData:
        """Return the coordinator data."""
        return self.coordinator.data
