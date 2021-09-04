"""Sensor platform for the PoolSense sensor."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_EMAIL,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    ELECTRIC_POTENTIAL_MILLIVOLT,
    PERCENTAGE,
    TEMP_CELSIUS,
)

from . import PoolSenseEntity
from .const import ATTRIBUTION, DOMAIN

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="Chlorine",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_MILLIVOLT,
        icon="mdi:pool",
        name="Chlorine",
        device_class=None,
    ),
    SensorEntityDescription(
        key="pH",
        native_unit_of_measurement=None,
        icon="mdi:pool",
        name="pH",
        device_class=None,
    ),
    SensorEntityDescription(
        key="Battery",
        native_unit_of_measurement=PERCENTAGE,
        icon=None,
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
        key="Last Seen",
        native_unit_of_measurement=None,
        icon="mdi:clock",
        name="Last Seen",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    SensorEntityDescription(
        key="Chlorine High",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_MILLIVOLT,
        icon="mdi:pool",
        name="Chlorine High",
        device_class=None,
    ),
    SensorEntityDescription(
        key="Chlorine Low",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_MILLIVOLT,
        icon="mdi:pool",
        name="Chlorine Low",
        device_class=None,
    ),
    SensorEntityDescription(
        key="pH High",
        native_unit_of_measurement=None,
        icon="mdi:pool",
        name="pH High",
        device_class=None,
    ),
    SensorEntityDescription(
        key="pH Low",
        native_unit_of_measurement=None,
        icon="mdi:pool",
        name="pH Low",
        device_class=None,
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer sensor setup to the shared sensor module."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        PoolSenseSensor(coordinator, config_entry.data[CONF_EMAIL], description)
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities, False)


class PoolSenseSensor(PoolSenseEntity, SensorEntity):
    """Sensor representing poolsense data."""

    _attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}

    def __init__(self, coordinator, email, description: SensorEntityDescription):
        """Initialize PoolSense sensor."""
        super().__init__(coordinator, email, description)
        self._attr_name = f"PoolSense {description.name}"

    @property
    def native_value(self):
        """State of the sensor."""
        return self.coordinator.data[self.entity_description.key]
