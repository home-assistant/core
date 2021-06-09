#!/usr/bin/env python3
"""Tuya Home Assistant Base Device Model."""
from __future__ import annotations

from tuya_iot import TuyaDevice, TuyaDeviceManager

from .const import DOMAIN


class TuyaHaDevice:
    """Tuya base device."""

    def __init__(self, device: TuyaDevice, device_manager: TuyaDeviceManager):
        """Init TuyaHaDevice."""
        super().__init__()
        self.tuya_device = device
        self.tuya_device_manager = device_manager
        self.entity_id = f"tuya_v2.{device.id}"

    @staticmethod
    def remap(old_value, old_min, old_max, new_min, new_max):
        """Remap old_value to new_value."""
        new_value = ((old_value - old_min) / (old_max - old_min)) * (
            new_max - new_min
        ) + new_min
        return new_value

    @property
    def should_poll(self) -> bool:
        """Hass should not poll."""
        return False

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return f"tuya_{self.tuya_device.uuid}"

    @property
    def name(self) -> str | None:
        """Return Tuya device name."""
        return self.tuya_device.name

    @property
    def device_info(self):
        """Return a device description for device registry."""
        _device_info = {
            "identifiers": {(DOMAIN, f"{self.tuya_device.uuid}")},
            "manufacturer": "tuya",
            "name": self.tuya_device.name,
            "model": self.tuya_device.product_name,
        }
        return _device_info

    # @property
    # def icon(self) -> Optional[str]:
    #     """Return Tuya device icon."""
    #     cdn_url = 'https://images.tuyacn.com/'
    #     # TODO customize cdn url
    #     return cdn_url + self.tuyaDevice.icon

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self.tuya_device.online
