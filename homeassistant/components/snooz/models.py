"""Data models for the Snooz component."""

from dataclasses import dataclass

from bleak.backends.device import BLEDevice
from pysnooz import SnoozAdvertisementData, SnoozDevice, SnoozDeviceCharacteristicData

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo

from .const import DOMAIN, MODEL_NAMES


@dataclass
class SnoozConfigurationData:
    """Configuration data for Snooz."""

    ble_device: BLEDevice
    adv_data: SnoozAdvertisementData
    info: SnoozDeviceCharacteristicData
    device: SnoozDevice
    title: str

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device info for device registry."""
        return DeviceInfo(
            name=self.title,
            manufacturer=self.info.manufacturer,
            model=MODEL_NAMES[self.adv_data.model],
            connections={(CONNECTION_BLUETOOTH, self.device.address)},
            identifiers={(DOMAIN, self.device.address)},
            hw_version=self.info.hardware,
            sw_version=self.info.software or self.info.firmware,
        )
