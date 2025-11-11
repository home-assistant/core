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
    SensorStateClass,
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
    is_available_fn: Callable[[AmazonDevice, str], bool] = lambda device, key: (
        device.online
        and (sensor := device.sensors.get(key)) is not None
        and sensor.error is False
    )


SENSORS: Final = (
    AmazonSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement_fn=lambda device, key: (
            UnitOfTemperature.CELSIUS
            if key in device.sensors and device.sensors[key].scale == "CELSIUS"
            else UnitOfTemperature.FAHRENHEIT
        ),
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AmazonSensorEntityDescription(
        key="illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Amazon Devices sensors based on a config entry."""

    coordinator = entry.runtime_data

    known_devices: set[str] = set()

    def _check_device() -> None:
        current_devices = set(coordinator.data)
        new_devices = current_devices - known_devices
        if new_devices:
            known_devices.update(new_devices)
            async_add_entities(
                AmazonSensorEntity(coordinator, serial_num, sensor_desc)
                for sensor_desc in SENSORS
                for serial_num in new_devices
                if coordinator.data[serial_num].sensors.get(sensor_desc.key) is not None
            )

    _check_device()
    entry.async_on_unload(coordinator.async_add_listener(_check_device))


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

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.entity_description.is_available_fn(
                self.device, self.entity_description.key
            )
            and super().available
        )
