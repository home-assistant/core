"""Support for myStrom sensors of switches/plugs."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pymystrom.switch import MyStromSwitch

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER


@dataclass(frozen=True)
class MyStromSwitchSensorEntityDescription(SensorEntityDescription):
    """Class describing mystrom switch sensor entities."""

    value_fn: Callable[[MyStromSwitch], float | None] = lambda _: None


SENSOR_TYPES: tuple[MyStromSwitchSensorEntityDescription, ...] = (
    MyStromSwitchSensorEntityDescription(
        key="consumption",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda device: device.consumption,
    ),
    MyStromSwitchSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda device: device.temperature,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the myStrom entities."""
    device: MyStromSwitch = hass.data[DOMAIN][entry.entry_id].device
    sensors = []

    for description in SENSOR_TYPES:
        if description.value_fn(device) is not None:
            sensors.append(MyStromSwitchSensor(device, entry.title, description))

    async_add_entities(sensors)


class MyStromSwitchSensor(SensorEntity):
    """Representation of the consumption or temperature of a myStrom switch/plug."""

    entity_description: MyStromSwitchSensorEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        device: MyStromSwitch,
        name: str,
        description: MyStromSwitchSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.device = device
        self.entity_description = description

        self._attr_unique_id = f"{device.mac}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.mac)},
            name=name,
            manufacturer=MANUFACTURER,
            sw_version=device.firmware,
        )

    @property
    def native_value(self) -> float | None:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(self.device)
