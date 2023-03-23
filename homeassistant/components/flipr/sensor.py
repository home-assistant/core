"""Sensor platform for the Flipr's pool_sensor."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfElectricPotential, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FliprEntity
from .const import DOMAIN

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="chlorine",
        name="Chlorine",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        icon="mdi:pool",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ph",
        name="pH",
        icon="mdi:pool",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temperature",
        name="Water Temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="date_time",
        name="Last Measured",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="red_ox",
        name="Red OX",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        icon="mdi:pool",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="battery",
        name="Battery Level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Defer sensor setup to the shared sensor module."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    sensors = [FliprSensor(coordinator, description) for description in SENSOR_TYPES]
    async_add_entities(sensors)


class FliprSensor(FliprEntity, SensorEntity):
    """Sensor representing FliprSensor data."""

    @property
    def native_value(self) -> str:
        """State of the sensor."""
        return self.coordinator.data[self.entity_description.key]
