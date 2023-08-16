"""Support for Honeywell (US) Total Connect Comfort sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aiosomecomfort.device import Device

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

<<<<<<< HEAD
from . import HoneywellData
from .const import DOMAIN, HUMIDITY_STATUS_KEY, TEMPERATURE_STATUS_KEY
=======
from .const import (
    CURRENT_HUMIDITY_STATUS_KEY,
    CURRENT_TEMPERATURE_STATUS_KEY,
    DOMAIN,
    OUTDOOR_HUMIDITY_STATUS_KEY,
    OUTDOOR_TEMPERATURE_STATUS_KEY,
)
>>>>>>> dde6ce6a996 (Add unit tests)


def _get_temperature_sensor_unit(device: Device) -> str:
    """Get the correct temperature unit for the device."""
    if device.temperature_unit == "C":
        return UnitOfTemperature.CELSIUS
    return UnitOfTemperature.FAHRENHEIT


@dataclass
class HoneywellSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Device], Any]
    unit_fn: Callable[[Device], Any]


@dataclass
class HoneywellSensorEntityDescription(
    SensorEntityDescription, HoneywellSensorEntityDescriptionMixin
):
    """Describes a Honeywell sensor entity."""


SENSOR_TYPES: tuple[HoneywellSensorEntityDescription, ...] = (
    HoneywellSensorEntityDescription(
<<<<<<< HEAD
        key=TEMPERATURE_STATUS_KEY,
=======
        key=OUTDOOR_TEMPERATURE_STATUS_KEY,
>>>>>>> dde6ce6a996 (Add unit tests)
        translation_key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.outdoor_temperature,
        unit_fn=_get_temperature_sensor_unit,
    ),
    HoneywellSensorEntityDescription(
<<<<<<< HEAD
        key=HUMIDITY_STATUS_KEY,
=======
        key=OUTDOOR_HUMIDITY_STATUS_KEY,
>>>>>>> dde6ce6a996 (Add unit tests)
        translation_key="outdoor_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.outdoor_humidity,
        unit_fn=lambda device: PERCENTAGE,
    ),
<<<<<<< HEAD
=======
    HoneywellSensorEntityDescription(
        key=CURRENT_TEMPERATURE_STATUS_KEY,
        translation_key="current_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.current_temperature,
        unit_fn=_get_temperature_sensor_unit,
    ),
    HoneywellSensorEntityDescription(
        key=CURRENT_HUMIDITY_STATUS_KEY,
        translation_key="current_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.current_humidity,
        unit_fn=lambda device: PERCENTAGE,
    ),
>>>>>>> dde6ce6a996 (Add unit tests)
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Honeywell thermostat."""
<<<<<<< HEAD
    data: HoneywellData = hass.data[DOMAIN][config_entry.entry_id]
=======
    data = hass.data[DOMAIN][config_entry.entry_id]
>>>>>>> dde6ce6a996 (Add unit tests)
    sensors = []

    for device in data.devices.values():
        for description in SENSOR_TYPES:
            if getattr(device, description.key) is not None:
                sensors.append(HoneywellSensor(device, description))

    async_add_entities(sensors)


class HoneywellSensor(SensorEntity):
    """Representation of a Honeywell US Outdoor Temperature Sensor."""

    entity_description: HoneywellSensorEntityDescription
    _attr_has_entity_name = True

<<<<<<< HEAD
    def __init__(self, device, description):
=======
    def __init__(self, device, description) -> None:
>>>>>>> dde6ce6a996 (Add unit tests)
        """Initialize the outdoor temperature sensor."""
        self._device = device
        self.entity_description = description
        self._attr_unique_id = f"{device.deviceid}_{description.key}"
        self._attr_native_unit_of_measurement = description.unit_fn(device)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.deviceid)},
            name=device.name,
            manufacturer="Honeywell",
        )

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.entity_description.value_fn(self._device)
