"""Support for sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

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

    native_unit_of_measurement_fn: Callable[[AmazonDevice, str], str] | None = None


SENSORS: Final = (
    AmazonSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement_fn=lambda device, _key: (
            UnitOfTemperature.CELSIUS
            if device.sensors[_key].scale == "CELSIUS"
            else UnitOfTemperature.FAHRENHEIT
        ),
    ),
    AmazonSensorEntityDescription(
        key="illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Amazon Devices sensors based on a config entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        AmazonSensorEntity(coordinator, serial_num, sensor_desc)
        for sensor_desc in SENSORS
        for serial_num in coordinator.data
        if coordinator.data[serial_num].sensors.get(sensor_desc.key) is not None
    )


class AmazonSensorEntity(AmazonEntity, SensorEntity):
    """Sensor device."""

    entity_description: AmazonSensorEntityDescription

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor."""
        if self.entity_description.native_unit_of_measurement_fn:
            return self.entity_description.native_unit_of_measurement_fn(
                self.device, self.entity_description.key
            )

        return super().native_unit_of_measurement

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.device.sensors[self.entity_description.key].value
