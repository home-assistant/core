"""Base entity for Zinvolt integration."""

from zinvolt.models import Unit

from homeassistant.const import ATTR_VIA_DEVICE
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BatteryData, ZinvoltDeviceCoordinator


class ZinvoltEntity(CoordinatorEntity[ZinvoltDeviceCoordinator]):
    """Base entity for Zinvolt integration."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ZinvoltDeviceCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.battery.serial_number)},
            manufacturer="Zinvolt",
            name=coordinator.battery.name,
            serial_number=coordinator.data.battery.serial_number,
        )


class ZinvoltUnitEntity(ZinvoltEntity):
    """Base entity for Zinvolt units."""

    def __init__(
        self, coordinator: ZinvoltDeviceCoordinator, unit_serial_number: str
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.unit_serial_number = unit_serial_number
        is_main_device = (
            list(coordinator.battery_units).index(self.unit_serial_number) == 0
        )
        self.serial_number = (
            coordinator.data.battery.serial_number
            if is_main_device
            else self.battery_unit.serial_number
        )
        name = coordinator.battery.name if is_main_device else self.battery_unit.name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.serial_number)},
            manufacturer="Zinvolt",
            name=name,
            serial_number=self.serial_number,
            sw_version=self.battery_unit.version.current_version,
            model_id=self.battery.model,
        )
        if not is_main_device:
            self._attr_device_info[ATTR_VIA_DEVICE] = (
                DOMAIN,
                coordinator.data.battery.serial_number,
            )

    @property
    def battery(self) -> BatteryData:
        """Return the battery data."""
        return self.coordinator.data.batteries[self.unit_serial_number]

    @property
    def battery_unit(self) -> Unit:
        """Return the battery unit."""
        return self.coordinator.battery_units[self.unit_serial_number]

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return (
            super().available
            and self.unit_serial_number in self.coordinator.data.batteries
        )
