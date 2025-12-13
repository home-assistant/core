"""Sensor platform for Actron Air integration."""

from actron_neo_api import ActronAirPeripheral

from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ActronAirSystemCoordinator


class ActronAirAcSensor(CoordinatorEntity[ActronAirSystemCoordinator]):
    """Base class for Actron Air sensors."""

    _attr_entity_category: EntityCategory | None = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(self, coordinator: ActronAirSystemCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._status = self.coordinator.data
        self._serial_number = coordinator.serial_number

        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, self._serial_number)},
            name=self._status.ac_system.system_name,
            manufacturer="Actron Air",
            model_id=self._status.ac_system.master_wc_model,
            sw_version=self._status.ac_system.master_wc_firmware_version,
            serial_number=self._serial_number,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return not self.coordinator.is_device_stale()


class ActronAirPeripheralSensor(ActronAirAcSensor):
    """Base class for Actron Air peripheral sensors."""

    _attr_entity_category = None

    def __init__(
        self, coordinator: ActronAirSystemCoordinator, peripheral: ActronAirPeripheral
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._ac_serial = coordinator.serial_number
        self._peripheral = peripheral
        self._serial_number = peripheral.serial_number

        suggested_area = None
        if hasattr(peripheral, "zones") and len(peripheral.zones) == 1:
            zone = peripheral.zones[0]
            if hasattr(zone, "title") and zone.title:
                suggested_area = zone.title

        self._attr_device_info: DeviceInfo = DeviceInfo(
            identifiers={(DOMAIN, self._serial_number)},
            name=f"{peripheral.device_type} {peripheral.logical_address}",
            model=peripheral.device_type,
            suggested_area=suggested_area,
            via_device=(DOMAIN, self._ac_serial),
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return not self.coordinator.is_device_stale()
