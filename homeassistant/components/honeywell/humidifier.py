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

    current_humidity: Callable[[Device], Any] | None = None
    humidity: Callable[[Device], Any] | None = None

    # value_fn: Callable[[Device], Any]
    # unit_fn: Callable[[Device], Any]


HUMIDIFIERS: dict[str, HoneywellHumidifierEntityDescription] = {
    "Humidifier": HoneywellHumidifierEntityDescription(
        key=HUMIDIFIER_KEY,
        current_humidity=lambda device: device.current_humidity,
        humidity=lambda device: device.set_humidifier_setpoint,
        device_class=HumidifierDeviceClass.HUMIDIFIER,
    ),
    "Dehumidifier": HoneywellHumidifierEntityDescription(
        key=DEHUMIDIFIER_KEY,
        current_humidity=lambda device: device.current_humidity,
        humidity=lambda device: device.set_dehumidifier_setpoint,
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

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.deviceid)},
            name=device.name,
            manufacturer="Honeywell",
        )


# Look at Tuya humidifier for help....
