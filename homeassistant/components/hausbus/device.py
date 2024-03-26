"""Representation of a Haus-Bus device."""
from pyhausbus.de.hausbus.homeassistant.proxy.controller.params.EFirmwareId import (
    EFirmwareId,
)

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


class HausbusDevice:
    """Common base for Haus-Bus devices."""

    def __init__(
        self,
        bridge_id: str,
        device_id: str,
        sw_version: str,
        hw_version: str,
        firmware_id: EFirmwareId,
    ) -> None:
        """Set up Haus-Bus device."""
        self._device_id = device_id
        self.manufacturer = "Haus-Bus.de"
        self.model_id = "Controller"
        self.name = f"Controller ID {self._device_id}"
        self.software_version = sw_version
        self.hardware_version = hw_version
        self.bridge_id = bridge_id
        self.firmware_id = firmware_id

    @property
    def device_id(self) -> str | None:
        """Return a serial number for this device."""
        return self._device_id

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return a device description for device registry."""
        if self.device_id is None:
            return None

        return DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            manufacturer=self.manufacturer,
            model=self.model_id,
            name=self.name,
            sw_version=self.software_version,
            hw_version=self.hardware_version,
            via_device=(DOMAIN, self.bridge_id),
        )

    def set_type(self, type_id: int):
        """Set device name and model_id according to device type."""
        match self.firmware_id:
            case EFirmwareId.ESP32:
                match type_id:
                    case 0x65:
                        self.model_id = "LAN-RS485 Brückenmodul"
                    case 0x18:
                        self.model_id = "6-fach Taster"
                    case 0x19:
                        self.model_id = "4-fach Taster"
                    case 0x1A:
                        self.model_id = "2-fach Taster"
                    case 0x1B:
                        self.model_id = "1-fach Taster"
                    case 0x1C:
                        self.model_id = "6-fach Taster Gira"
                    case 0x20:
                        self.model_id = "32-fach IO"
                    case 0x0C:
                        self.model_id = "16-fach Relais"
                    case 0x08:
                        self.model_id = "8-fach Relais"
                    case 0x10:
                        self.model_id = "22-fach UP-IO"
                    case 0x28:
                        self.model_id = "8-fach Dimmer"
                    case 0x30:
                        self.model_id = "2-fach RGB Dimmer"
                    case 0x00:
                        self.model_id = "4-fach 0-10V Dimmer"
                    case 0x01:
                        self.model_id = "4-fach 1-10V Dimmer"
                    case _:
                        self.model_id = "Controller"
            case EFirmwareId.HBC:
                match type_id:
                    case 0x18:
                        self.model_id = "6-fach Taster"
                    case 0x19:
                        self.model_id = "4-fach Taster"
                    case 0x1A:
                        self.model_id = "2-fach Taster"
                    case 0x1B:
                        self.model_id = "1-fach Taster"
                    case 0x1C:
                        self.model_id = "6-fach Taster Gira"
                    case 0x20:
                        self.model_id = "32-fach IO"
                    case 0x0C:
                        self.model_id = "16-fach Relais"
                    case 0x08:
                        self.model_id = "8-fach Relais"
                    case 0x10:
                        self.model_id = "24-fach UP-IO"
                    case 0x28:
                        self.model_id = "8-fach Dimmer"
                    case 0x29:
                        self.model_id = "8-fach Dimmer"
                    case 0x30:
                        self.model_id = "2-fach RGB Dimmer"
                    case 0x00:
                        self.model_id = "4-fach 0-10V Dimmer"
                    case 0x01:
                        self.model_id = "4-fach 1-10V Dimmer"
                    case _:
                        self.model_id = "Controller"
            case EFirmwareId.SD485:
                match type_id:
                    case 0x28:
                        self.model_id = "24-fach UP-IO"
                    case 0x1E:
                        self.model_id = "6-fach Taster"
                    case 0x2E:
                        self.model_id = "6-fach Taster"
                    case 0x2F:
                        self.model_id = "6-fach Taster"
                    case 0x2B:
                        self.model_id = "4-fach 0-10V Dimmer"
                    case 0x2C:
                        self.model_id = "4-fach Taster"
                    case 0x2D:
                        self.model_id = "4-fach 1-10V Dimmer"
                    case 0x2A:
                        self.model_id = "2-fach Taster"
                    case 0x29:
                        self.model_id = "1-fach Taster"
                    case _:
                        self.model_id = "Controller"
            case EFirmwareId.AR8:
                match type_id:
                    case 0x28:
                        self.model_id = "LAN Brückenmodul"
                    case 0x30:
                        self.model_id = "8-fach Relais"
                    case _:
                        self.model_id = "Controller"
            case EFirmwareId.SD6:
                match type_id:
                    case 0x14:
                        self.model_id = "Multitaster"
                    case 0x1E:
                        self.model_id = "Multitaster"
                    case _:
                        self.model_id = "Controller"
        self.name = f"{self.model_id} ID {self._device_id}"
