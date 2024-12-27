"""Fujitsu FGlair base entity."""

from ayla_iot_unofficial.fujitsu_hvac import FujitsuHVAC

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FGLairCoordinator


class FGLairEntity(CoordinatorEntity[FGLairCoordinator]):
    """Generic Fglair entity (base class)."""

    def __init__(self, coordinator: FGLairCoordinator, device: FujitsuHVAC) -> None:
        """Store the representation of the device."""
        super().__init__(coordinator, context=device.device_serial_number)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_serial_number)},
            name=device.device_name,
            manufacturer="Fujitsu",
            model=device.property_values["model_name"],
            serial_number=device.device_serial_number,
            sw_version=device.property_values["mcu_firmware_version"],
        )

    @property
    def device(self) -> FujitsuHVAC:
        """Return the device object from the coordinator data."""
        return self.coordinator.data[self.coordinator_context]
