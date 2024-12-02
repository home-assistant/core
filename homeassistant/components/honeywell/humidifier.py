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
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HoneywellData
from .const import DOMAIN

HUMIDIFIER_KEY = "humidifier"
DEHUMIDIFIER_KEY = "dehumidfier"


@dataclass(frozen=True, kw_only=True)
class HoneywellHumidifierEntityDescription(HumidifierEntityDescription):
    """Describes a Honeywell sensor entity."""

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
        current_humidity=lambda device: device.current_humidity,
        set_humidity=lambda device, humidity: device.set_humidifier_setpoint(humidity),
        min_humidity=lambda device: device.humidifier_lower_limit,
        max_humidity=lambda device: device.humidifier_upper_limit,
        current_set_humidity=lambda device: device.humidifier_setpoint,
        mode=lambda device: device.humidifer_mode,
        off=lambda device: device.set_dehumidifer_off,
        on=lambda device: device.set_dehumidifer_auto,
        device_class=HumidifierDeviceClass.HUMIDIFIER,
    ),
    "Dehumidifier": HoneywellHumidifierEntityDescription(
        key=DEHUMIDIFIER_KEY,
        current_humidity=lambda device: device.current_humidity,
        set_humidity=lambda device, humidity: device.set_dehumidifier_setpoint(
            humidity
        ),
        min_humidity=lambda device: device.dehumidifier_lower_limit,
        max_humidity=lambda device: device.dehumidifier_upper_limit,
        current_set_humidity=lambda device: device.dehumidifier_setpoint,
        mode=lambda device: device.dehumidifer_mode,
        off=lambda device: device.set_dehumidifer_off,
        on=lambda device: device.set_dehumidifer_auto,
        device_class=HumidifierDeviceClass.DEHUMIDIFIER,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Honeywell (de)humidifier dynamically."""
    # hass_data = config_entry.runtime_data
    data: HoneywellData = hass.data[DOMAIN][config_entry.entry_id]
    entities: list = []
    for device in data.devices.values():
        if device.has_humidifer:
            entities.append(HoneywellHumidifier(device, HUMIDIFIERS["Humidifier"]))
        if device.has_dehumidifier:
            entities.append(HoneywellHumidifier(device, HUMIDIFIERS["Dehumidifier"]))

    async_add_entities(entities)


class HoneywellHumidifier(HumidifierEntity):
    """Representation of a Honeywell US (De)Humidifier."""

    entity_description: HoneywellHumidifierEntityDescription
    _attr_has_entity_name = True

    def __init__(self, device, description) -> None:
        """Initialize the (De)Humidifier."""
        self._device = device
        self.entity_description = description
        self._attr_unique_id = f"{device.deviceid}_{description.key}"
        self._attr_native_unit_of_measurement = description.unit_fn(device)
        self._set_humidity = description.current_set_humidity(device)
        self._attr_min_humidity = description.min_humidity(device)
        self._attr_max_humidity = description.max_humidity(device)
        self._current_humidity = description.current_humidity(device)
        self._mode = description.mode(device)
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
    def mode(self) -> str | None:
        """Return the current mode."""
        return self.entity_description.mode(self._device)

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity we try to reach."""
        if self._set_humidity is None:
            return None

        humidity = self.entity_description.current_set_humidity(self._device)
        if humidity is None:
            return None

        return humidity

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        if self._current_humidity is None:
            return None
        return self.entity_description.current_humidity(self._device)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self.entity_description.on(self._device)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self.entity_description.off(self._device)

    def set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        if self._set_humidity is None:
            raise RuntimeError(
                "Cannot set humidity, device doesn't provide methods to set it"
            )
        self.entity_description.set_humidity(self._device, humidity)


# Look at Tuya humidifier for help....
