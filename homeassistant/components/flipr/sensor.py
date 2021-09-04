"""Sensor platform for the Flipr's pool_sensor."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    ELECTRIC_POTENTIAL_MILLIVOLT,
    TEMP_CELSIUS,
)

from . import FliprEntity
from .const import ATTRIBUTION, CONF_FLIPR_ID, DOMAIN

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="chlorine",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_MILLIVOLT,
        icon="mdi:pool",
        name="Chlorine",
        device_class=None,
    ),
    SensorEntityDescription(
        key="ph",
        native_unit_of_measurement=None,
        icon="mdi:pool",
        name="pH",
        device_class=None,
    ),
    SensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        icon=None,
        name="Water Temp",
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key="date_time",
        native_unit_of_measurement=None,
        icon=None,
        name="Last Measured",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    SensorEntityDescription(
        key="red_ox",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_MILLIVOLT,
        icon="mdi:pool",
        name="Red OX",
        device_class=None,
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer sensor setup to the shared sensor module."""
    flipr_id = config_entry.data[CONF_FLIPR_ID]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        FliprSensor(coordinator, flipr_id, description) for description in SENSOR_TYPES
    ]

    async_add_entities(entities, True)


class FliprSensor(FliprEntity, SensorEntity):
    """Sensor representing FliprSensor data."""

    _attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}

    def __init__(self, coordinator, flipr_id, description: SensorEntityDescription):
        """Initialize Flipr sensor."""
        super().__init__(coordinator, flipr_id, description)
        self._attr_name = f"Flipr {self.flipr_id} {description.name}"

    @property
    def native_value(self):
        """State of the sensor."""
        state = self.coordinator.data[self.entity_description.key]
        if isinstance(state, datetime):
            return state.isoformat()
        return state
