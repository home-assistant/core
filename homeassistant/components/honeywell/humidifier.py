"""Support for Honeywell (de)humidifiers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aiosomecomfort.device import Device

from homeassistant.components.humidifier import (
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HoneywellConfigEntry
from .const import DOMAIN

HUMIDIFIER_KEY = "humidifier"
DEHUMIDIFIER_KEY = "dehumidifier"


@dataclass(frozen=True, kw_only=True)
class HoneywellHumidifierEntityDescription(HumidifierEntityDescription):
    """Describes a Honeywell humidifier entity."""

    current_humidity: Callable[[Device], Any]
    current_set_humidity: Callable[[Device], Any]
    max_humidity: Callable[[Device], Any]
    min_humidity: Callable[[Device], Any]
    set_humidity: Callable[[Device, Any], Any]
    mode: Callable[[Device], Any]
    off: Callable[[Device], Any]
    on: Callable[[Device], Any]


HUMIDIFIERS: dict[str, HoneywellHumidifierEntityDescription] = {
    "Humidifier": HoneywellHumidifierEntityDescription(
        key=HUMIDIFIER_KEY,
        translation_key=HUMIDIFIER_KEY,
        current_humidity=lambda device: device.current_humidity,
        set_humidity=lambda device, humidity: device.set_humidifier_setpoint(humidity),
        min_humidity=lambda device: device.humidifier_lower_limit,
        max_humidity=lambda device: device.humidifier_upper_limit,
        current_set_humidity=lambda device: device.humidifier_setpoint,
        mode=lambda device: device.humidifier_mode,
        off=lambda device: device.set_humidifier_off(),
        on=lambda device: device.set_humidifier_auto(),
        device_class=HumidifierDeviceClass.HUMIDIFIER,
    ),
    "Dehumidifier": HoneywellHumidifierEntityDescription(
        key=DEHUMIDIFIER_KEY,
        translation_key=DEHUMIDIFIER_KEY,
        current_humidity=lambda device: device.current_humidity,
        set_humidity=lambda device, humidity: device.set_dehumidifier_setpoint(
            humidity
        ),
        min_humidity=lambda device: device.dehumidifier_lower_limit,
        max_humidity=lambda device: device.dehumidifier_upper_limit,
        current_set_humidity=lambda device: device.dehumidifier_setpoint,
        mode=lambda device: device.dehumidifier_mode,
        off=lambda device: device.set_dehumidifier_off(),
        on=lambda device: device.set_dehumidifier_auto(),
        device_class=HumidifierDeviceClass.DEHUMIDIFIER,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HoneywellConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Honeywell (de)humidifier dynamically."""
    data = config_entry.runtime_data
    entities: list = []
    for device in data.devices.values():
        if device.has_humidifier:
            entities.append(HoneywellHumidifier(device, HUMIDIFIERS["Humidifier"]))
        if device.has_dehumidifier:
            entities.append(HoneywellHumidifier(device, HUMIDIFIERS["Dehumidifier"]))

    async_add_entities(entities)


class HoneywellHumidifier(HumidifierEntity):
    """Representation of a Honeywell US (De)Humidifier."""

    entity_description: HoneywellHumidifierEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self, device: Device, description: HoneywellHumidifierEntityDescription
    ) -> None:
        """Initialize the (De)Humidifier."""
        self._device = device
        self.entity_description = description
        self._attr_unique_id = f"{device.deviceid}_{description.key}"
        self._attr_min_humidity = description.min_humidity(device)
        self._attr_max_humidity = description.max_humidity(device)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.deviceid)},
            name=device.name,
            manufacturer="Honeywell",
        )

    @property
    def is_on(self) -> bool:
        """Return the device is on or off."""
        return self.entity_description.mode(self._device) != 0

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity we try to reach."""
        return self.entity_description.current_set_humidity(self._device)

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self.entity_description.current_humidity(self._device)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.entity_description.on(self._device)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.entity_description.off(self._device)

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self.entity_description.set_humidity(self._device, humidity)
