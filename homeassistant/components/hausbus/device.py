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

    def set_type(self, type_id: int) -> None:
        """Set device name and model_id according to device type."""
        model_ids = {
            EFirmwareId.ESP32: {
                int("0x65", 16): "LAN-RS485 Brückenmodul",
                int("0x18", 16): "6-fach Taster",
                int("0x19", 16): "4-fach Taster",
                int("0x1A", 16): "2-fach Taster",
                int("0x1B", 16): "1-fach Taster",
                int("0x1C", 16): "6-fach Taster Gira",
                int("0x20", 16): "32-fach IO",
                int("0x0C", 16): "16-fach Relais",
                int("0x08", 16): "8-fach Relais",
                int("0x10", 16): "22-fach UP-IO",
                int("0x28", 16): "8-fach Dimmer",
                int("0x30", 16): "2-fach RGB Dimmer",
                int("0x00", 16): "4-fach 0-10V Dimmer",
                int("0x01", 16): "4-fach 1-10V Dimmer",
            },
            EFirmwareId.HBC: {
                int("0x18", 16): "6-fach Taster",
                int("0x19", 16): "4-fach Taster",
                int("0x1A", 16): "2-fach Taster",
                int("0x1B", 16): "1-fach Taster",
                int("0x1C", 16): "6-fach Taster Gira",
                int("0x20", 16): "32-fach IO",
                int("0x0C", 16): "16-fach Relais",
                int("0x08", 16): "8-fach Relais",
                int("0x10", 16): "22-fach UP-IO",
                int("0x28", 16): "8-fach Dimmer",
                int("0x30", 16): "2-fach RGB Dimmer",
                int("0x00", 16): "4-fach 0-10V Dimmer",
                int("0x01", 16): "4-fach 1-10V Dimmer",
            },
            EFirmwareId.SD485: {
                int("0x28", 16): "24-fach UP-IO",
                int("0x1E", 16): "6-fach Taster",
                int("0x2E", 16): "6-fach Taster",
                int("0x2F", 16): "6-fach Taster",
                int("0x2B", 16): "4-fach 0-10V Dimmer",
                int("0x2C", 16): "4-fach Taster",
                int("0x2D", 16): "4-fach 1-10V Dimmer",
                int("0x2A", 16): "2-fach Taster",
                int("0x29", 16): "1-fach Taster",
            },
            EFirmwareId.AR8: {
                int("0x28", 16): "LAN Brückenmodul",
                int("0x30", 16): "8-fach Relais",
            },
            EFirmwareId.SD6: {
                int("0x14", 16): "Multitaster",
                int("0x1E", 16): "Multitaster",
            },
        }
        firmware_model_id = model_ids.get(self.firmware_id, {})
        if len(firmware_model_id) == 0:
            self.model_id = "Controller"
        else:
            self.model_id = firmware_model_id.get(type_id, "Controller")
        self.name = f"{self.model_id} ID {self._device_id}"
