"""Sensor platform for the PoolSense sensor."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import (
    CONF_DEVICE_ID,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    ELECTRIC_POTENTIAL_MILLIVOLT,
    PERCENTAGE,
    TEMP_CELSIUS,
)

from . import PoolSenseEntity
from .const import DOMAIN

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="Chlorine",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_MILLIVOLT,
        icon="mdi:pool",
        name="Chlorine",
    ),
    SensorEntityDescription(
        key="Chlorine Instant",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_MILLIVOLT,
        icon="mdi:pool",
        name="Chlorine Instant",
    ),
    SensorEntityDescription(
        key="pH",
        icon="mdi:pool",
        name="pH",
    ),
    SensorEntityDescription(
        key="pH Instant",
        icon="mdi:pool",
        name="pH Instant",
    ),
    SensorEntityDescription(
        key="Battery",
        native_unit_of_measurement=PERCENTAGE,
        name="Battery",
        device_class=DEVICE_CLASS_BATTERY,
    ),
    SensorEntityDescription(
        key="Water Temp",
        native_unit_of_measurement=TEMP_CELSIUS,
        icon="mdi:coolant-temperature",
        name="Temperature",
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key="Water Temp Instant",
        native_unit_of_measurement=TEMP_CELSIUS,
        icon="mdi:coolant-temperature",
        name="Temperature Instant",
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key="Last Seen",
        icon="mdi:clock",
        name="Last Seen",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    SensorEntityDescription(
        key="Chlorine High",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_MILLIVOLT,
        icon="mdi:pool",
        name="Chlorine High",
    ),
    SensorEntityDescription(
        key="Chlorine Low",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_MILLIVOLT,
        icon="mdi:pool",
        name="Chlorine Low",
    ),
    SensorEntityDescription(
        key="pH High",
        icon="mdi:pool",
        name="pH High",
    ),
    SensorEntityDescription(
        key="pH Low",
        icon="mdi:pool",
        name="pH Low",
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer sensor setup to the shared sensor module."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        PoolSenseSensor(coordinator, config_entry.data[CONF_DEVICE_ID], description)
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities, False)


class PoolSenseSensor(PoolSenseEntity, SensorEntity):
    """Sensor representing poolsense data."""

    @property
    def name(self):
        """Return the name of the particular component."""
        return f"{self.device_id} PoolSense {SENSOR_TYPES[self.info_type]['name']}"

    @property
    def native_value(self):
        """State of the sensor."""
        return self.coordinator.data[self.entity_description.key]
