#!/usr/bin/env python3
"""Tuya Home Assistant Base Device Model."""
from __future__ import annotations

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class TuyaHaEntity(Entity):
    """Tuya base device."""

    def __init__(self, device: TuyaDevice, device_manager: TuyaDeviceManager) -> None:
        """Init TuyaHaEntity."""
        super().__init__()

        self.tuya_device = device
        self.tuya_device_manager = device_manager

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
        return f"tuya.{self.tuya_device.id}"

    @property
    def name(self) -> str | None:
        """Return Tuya device name."""
        return self.tuya_device.name

    @property
    def device_info(self):
        """Return a device description for device registry."""
        _device_info = {
            "identifiers": {(DOMAIN, f"{self.tuya_device.id}")},
            "manufacturer": "Tuya",
            "name": self.tuya_device.name,
            "model": self.tuya_device.product_name,
        }
        return _device_info

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self.tuya_device.online

    def _send_command(self, commands) -> None:
        self.hass.async_add_executor_job(
            self.tuya_device_manager.send_commands, self.tuya_device.id, commands
        )
