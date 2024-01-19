"""The Tesla Powerwall integration base entity."""
from typing import Optional

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
from .models import BatteryResponse, PowerwallData, PowerwallRuntimeData


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
        self.base_unique_id = base_info.gateway_din
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


class BatteryEntity(CoordinatorEntity[DataUpdateCoordinator[PowerwallData]]):
    """Base class for battery entities."""

    def __init__(
        self, powerwall_data: PowerwallRuntimeData, serial_number: str
    ) -> None:
        """Initialize the entity."""
        base_info = powerwall_data[POWERWALL_BASE_INFO]
        coordinator = powerwall_data[POWERWALL_COORDINATOR]
        assert coordinator is not None
        super().__init__(coordinator)
        self.serial_number = serial_number
        self.power_wall = powerwall_data[POWERWALL_API]
        self.base_unique_id = f"{base_info.gateway_din}_{serial_number}"

        battery: Optional[BatteryResponse] = None
        for b in base_info.batteries:
            if b.serial_number == serial_number:
                battery = b
        assert battery is not None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.base_unique_id)},
            manufacturer=MANUFACTURER,
            model=f"{MODEL} ({battery.part_number})",
            name=f"{base_info.site_info.site_name} {battery.serial_number}",
            sw_version=base_info.status.version,
            configuration_url=base_info.url,
            via_device=(DOMAIN, base_info.gateway_din),
        )

    @property
    def battery_data(self) -> BatteryResponse:
        """Return the coordinator data."""
        for battery in self.coordinator.data.batteries:
            if battery.serial_number == self.serial_number:
                return battery

        assert False

    @property
    def data(self) -> PowerwallData:
        """Return the coordinator data."""
        return self.coordinator.data
