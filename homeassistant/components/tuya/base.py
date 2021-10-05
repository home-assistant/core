"""Tuya Home Assistant Base Device Model."""
from __future__ import annotations

from typing import Any

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, TUYA_HA_SIGNAL_UPDATE_ENTITY


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
        return ((old_value - old_min) / (old_max - old_min)) * (
            new_max - new_min
        ) + new_min

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
        return {
            "identifiers": {(DOMAIN, f"{self.tuya_device.id}")},
            "manufacturer": "Tuya",
            "name": self.tuya_device.name,
            "model": self.tuya_device.product_name,
        }

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self.tuya_device.online

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{TUYA_HA_SIGNAL_UPDATE_ENTITY}_{self.tuya_device.id}",
                self.async_write_ha_state,
            )
        )

    def _send_command(self, commands: list[dict[str, Any]]) -> None:
        """Send command to the device."""
        self.tuya_device_manager.send_commands(self.tuya_device.id, commands)
