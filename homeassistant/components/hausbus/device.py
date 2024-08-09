"""Representation of a Haus-Bus device."""

from pyhausbus import HausBusDevice
from pyhausbus.de.hausbus.homeassistant.proxy.controller.params.EFirmwareId import (
    EFirmwareId,
)

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


class HausbusDevice:
    """Common base for Haus-Bus devices."""

    def __init__(
        self,
        device_id: str,
        sw_version: str,
        hw_version: str,
        firmware_id: EFirmwareId,
    ) -> None:
        """Set up Haus-Bus device."""
        self.device_id = device_id
        self.manufacturer = "Haus-Bus.de"
        self.model_id = "Controller"
        self.name = f"Controller {self.device_id}"
        self.software_version = sw_version
        self.hardware_version = hw_version
        self.firmware_id = firmware_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            manufacturer=self.manufacturer,
            model=self.model_id,
            name=self.name,
            sw_version=self.software_version,
            hw_version=self.hardware_version,
        )

    def set_type(self, type_id: int) -> None:
        """Set device name and model_id according to device type."""
        self.model_id = HausBusDevice.get_device_type(self.firmware_id, type_id)
        self.name = f"{self.model_id} {self.device_id}"
