"""Base entity for Mitsubishi Comfort Cloud integration."""

from mitsubishi_comfort import CloudIndoorUnit

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MitsubishiComfortCloudCoordinator


class MitsubishiComfortCloudEntity(
    CoordinatorEntity[MitsubishiComfortCloudCoordinator]
):
    """Base class for all Mitsubishi Comfort Cloud entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MitsubishiComfortCloudCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.serial)},
            name=device.name,
            manufacturer="Mitsubishi",
            serial_number=device.serial,
            sw_version=device.status.firmware_version,
            hw_version=device.status.hardware_version,
        )

    @property
    def _device(self) -> CloudIndoorUnit:
        """Return the underlying device from coordinator data."""
        return self.coordinator.data
