"""Representation of Venstar sensors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS, TEMP_FAHRENHEIT

from . import VenstarDataUpdateCoordinator, VenstarEntity
from .const import DOMAIN


@dataclass
class VenstarSensorEntityDescription(SensorEntityDescription):
    """Base description of a Sensor entity."""


HUMIDITY_SENSOR_DESCRIPTION = VenstarSensorEntityDescription(
    key="humidity",
    device_class=DEVICE_CLASS_HUMIDITY,
    state_class=STATE_CLASS_MEASUREMENT,
    native_unit_of_measurement=PERCENTAGE,
)
TEMPERATURE_SENSOR_DESCRIPTION = VenstarSensorEntityDescription(
    key="temperature",
    device_class=DEVICE_CLASS_TEMPERATURE,
    state_class=STATE_CLASS_MEASUREMENT,
)


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up Vensar device binary_sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[Any] = []

    sensors = coordinator.client.get_sensor_list()
    if not sensors:
        return

    # look for humidity, and temperature
    for sensor_name in sensors:
        if coordinator.client.get_sensor(sensor_name, "hum") is not None:
            entities.append(
                VenstarHumiditySensor(
                    coordinator,
                    config_entry,
                    HUMIDITY_SENSOR_DESCRIPTION,
                    sensor_name,
                )
            )
        if coordinator.client.get_sensor(sensor_name, "temp") is not None:
            entities.append(
                VenstarTemperatureSensor(
                    coordinator,
                    config_entry,
                    TEMPERATURE_SENSOR_DESCRIPTION,
                    sensor_name,
                )
            )

    async_add_entities(entities)


class VenstarSensor(VenstarEntity, SensorEntity):
    """Base class for a Venstar sensor."""

    entity_description: VenstarSensorEntityDescription

    def __init__(
        self,
        coordinator: VenstarDataUpdateCoordinator,
        config: ConfigEntry,
        entity_description: VenstarSensorEntityDescription,
        sensor_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config)
        self.entity_description = entity_description
        self.sensor_name = sensor_name
        self._config = config


class VenstarHumiditySensor(VenstarSensor):
    """Represent a Venstar humidity sensor."""

    @property
    def unique_id(self):
        """Return the unique id."""
        return f"{self._config.entry_id}_{self.sensor_name.replace(' ', '_')}_hum"

    @property
    def name(self):
        """Return the name of the device."""
        return f"{self._client.name} {self.sensor_name} Humidity"

    @property
    def native_value(self) -> int:
        """Return state of the sensor."""
        return self._client.get_sensor(self.sensor_name, "hum")


class VenstarTemperatureSensor(VenstarSensor):
    """Represent a Venstar temperature sensor."""

    @property
    def unique_id(self):
        """Return the unique id."""
        return f"{self._config.entry_id}_{self.sensor_name.replace(' ', '_')}_temp"

    @property
    def name(self):
        """Return the name of the device."""
        return (
            f"{self._client.name} {self.sensor_name.replace(' Temp', '')} Temperature"
        )

    @property
    def native_unit_of_measurement(self) -> str:
        """Return unit of measurement the value is expressed in."""
        if self._client.tempunits == self._client.TEMPUNITS_F:
            return TEMP_FAHRENHEIT
        return TEMP_CELSIUS

    @property
    def native_value(self) -> float:
        """Return state of the sensor."""
        return round(float(self._client.get_sensor(self.sensor_name, "temp")), 1)
