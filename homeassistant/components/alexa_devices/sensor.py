"""Support for sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, cast

from aioamazondevices.api import AmazonDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import LIGHT_LUX, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import AmazonConfigEntry
from .entity import AmazonEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AmazonSensorEntityDescription(SensorEntityDescription):
    """Amazon Devices sensor entity description."""

    is_supported: Callable[[AmazonDevice, str], bool] = lambda _device, _key: True


SENSORS: Final = (
    AmazonSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        is_supported=lambda _device, _key: _device.sensors.get(_key) is not None,
    ),
    AmazonSensorEntityDescription(
        key="illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        is_supported=lambda _device, _key: _device.sensors.get(_key) is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Amazon Devices sensors based on a config entry."""

    coordinator = entry.runtime_data

    x = [
        AmazonSensorEntity(coordinator, serial_num, sensor_desc)
        for sensor_desc in SENSORS
        for serial_num in coordinator.data
        if sensor_desc.is_supported(coordinator.data[serial_num], sensor_desc.key)
    ]
    async_add_entities(x)


class AmazonSensorEntity(AmazonEntity, SensorEntity):
    """Sensor device."""

    entity_description: AmazonSensorEntityDescription

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor."""
        if self.entity_description.key == "temperature":
            # Temperature sensor can have different scales
            if self.device.sensors[self.entity_description.key].scale == "CELSIUS":
                return UnitOfTemperature.CELSIUS
            return UnitOfTemperature.FAHRENHEIT

        if self.entity_description.key == "illuminance":
            # Illuminance sensor uses lux
            return LIGHT_LUX

        # No unit of measurement for other sensors
        return None

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return cast("StateType", self.device.sensors[self.entity_description.key].value)
