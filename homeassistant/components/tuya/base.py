"""Tuya Home Assistant Base Device Model."""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import Any

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN, TUYA_HA_SIGNAL_UPDATE_ENTITY

_LOGGER = logging.getLogger(__name__)


@dataclass
class IntegerTypeData:
    """Integer Type Data."""

    min: int
    max: int
    unit: str
    scale: float
    step: float

    @classmethod
    def from_json(cls, data: str) -> IntegerTypeData:
        """Load JSON string and return a IntegerTypeData object."""
        return cls(**json.loads(data))


@dataclass
class EnumTypeData:
    """Enum Type Data."""

    range: list[str]

    @classmethod
    def from_json(cls, data: str) -> EnumTypeData:
        """Load JSON string and return a EnumTypeData object."""
        return cls(**json.loads(data))


class TuyaEntity(Entity):
    """Tuya base device."""

    _attr_should_poll = False

    def __init__(self, device: TuyaDevice, device_manager: TuyaDeviceManager) -> None:
        """Init TuyaHaEntity."""
        self._attr_unique_id = f"tuya.{device.id}"
        self.tuya_device = device
        self.tuya_device_manager = device_manager

    @property
    def name(self) -> str | None:
        """Return Tuya device name."""
        if (
            hasattr(self, "entity_description")
            and self.entity_description.name is not None
        ):
            return f"{self.tuya_device.name} {self.entity_description.name}"
        return self.tuya_device.name

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.tuya_device.id)},
            manufacturer="Tuya",
            name=self.tuya_device.name,
            model=self.tuya_device.product_name,
        )

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self.tuya_device.online

    async def async_added_to_hass(self) -> None:
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
        _LOGGER.debug(
            "Sending commands for device %s: %s", self.tuya_device.id, commands
        )
        self.tuya_device_manager.send_commands(self.tuya_device.id, commands)

    @staticmethod
    def scale(value: float | int, scale: float | int) -> float:
        """Scale a value."""
        return value * 1.0 / (10 ** scale)
