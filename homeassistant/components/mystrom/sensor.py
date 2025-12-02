"""Support for myStrom sensors of switches/plugs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pymystrom.pir import MyStromPir
from pymystrom.switch import MyStromSwitch

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import LIGHT_LUX, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, MANUFACTURER
from .models import MyStromConfigEntry


@dataclass(frozen=True)
class MyStromSensorEntityDescription[_DeviceT](SensorEntityDescription):
    """Class describing mystrom sensor entities."""

    value_fn: Callable[[_DeviceT], float | None] = lambda _: None


SENSOR_TYPES_PIR: tuple[MyStromSensorEntityDescription[MyStromPir], ...] = (
    MyStromSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=(
            lambda device: (
                float(device.temperature_compensated)
                if device.temperature_compensated is not None
                else None
            )
        ),
    ),
    MyStromSensorEntityDescription(
        key="illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LIGHT_LUX,
        value_fn=(
            lambda device: (
                float(device.intensity) if device.intensity is not None else None
            )
        ),
    ),
)


SENSOR_TYPES_SWITCH: tuple[MyStromSensorEntityDescription[MyStromSwitch], ...] = (
    MyStromSensorEntityDescription(
        key="avg_consumption",
        translation_key="avg_consumption",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda device: device.consumedWs,
    ),
    MyStromSensorEntityDescription(
        key="consumption",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda device: device.consumption,
    ),
    MyStromSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda device: device.temperature,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyStromConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the myStrom entities."""
    device = entry.runtime_data.device
    info = entry.runtime_data.info

    match device:
        case MyStromPir():
            entities = [
                MyStromSensor(device, entry.title, description, info["mac"])
                for description in SENSOR_TYPES_PIR
                if description.value_fn(device) is not None
            ]
        case MyStromSwitch():
            entities = [
                MyStromSensor(device, entry.title, description, info["mac"])
                for description in SENSOR_TYPES_SWITCH
                if description.value_fn(device) is not None
            ]
        case _:
            entities = []
    async_add_entities(entities)


class MyStromSensor[_DeviceT](SensorEntity):
    """Representation of the consumption or temperature of a myStrom switch/plug."""

    entity_description: MyStromSensorEntityDescription[_DeviceT]

    _attr_has_entity_name = True

    def __init__(
        self,
        device: _DeviceT,
        name: str,
        description: MyStromSensorEntityDescription[_DeviceT],
        mac: str,
    ) -> None:
        """Initialize the sensor."""
        self.device = device
        self.entity_description = description

        self._attr_unique_id = f"{mac}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            connections={(CONNECTION_NETWORK_MAC, mac)},
            name=name,
            manufacturer=MANUFACTURER,
            sw_version=getattr(device, "firmware", None),
        )

    @property
    def native_value(self) -> float | None:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(self.device)
