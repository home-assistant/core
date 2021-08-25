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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import FliprEntity
from .const import ATTRIBUTION, CONF_FLIPR_ID, DOMAIN

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="chlorine",
        name="Chlorine",
        device_class=None,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_MILLIVOLT,
        icon="mdi:pool",
    ),
    SensorEntityDescription(
        key="ph",
        name="pH",
        device_class=None,
        native_unit_of_measurement=None,
        icon="mdi:pool",
    ),
    SensorEntityDescription(
        key="temperature",
        name="Water Temp",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        icon=None,
    ),
    SensorEntityDescription(
        key="date_time",
        name="Last Measured",
        device_class=DEVICE_CLASS_TIMESTAMP,
        native_unit_of_measurement=None,
        icon=None,
    ),
    SensorEntityDescription(
        key="red_ox",
        name="Red OX",
        device_class=None,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_MILLIVOLT,
        icon="mdi:pool",
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer sensor setup to the shared sensor module."""
    flipr_id = config_entry.data[CONF_FLIPR_ID]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    sensors = [
        FliprSensor(coordinator, flipr_id, description, config_entry.entry_id)
        for description in SENSOR_TYPES
    ]
    async_add_entities(sensors, True)


class FliprSensor(FliprEntity, SensorEntity):
    """Sensor representing FliprSensor data."""

    _attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        flipr_id: str,
        description: SensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize a Flipr sensor."""
        super().__init__(coordinator, flipr_id, f"{description.key}-{entry_id}")
        self.entity_description = description

    @property
    def name(self):
        """Return the name of the particular component."""
        return f"Flipr {self.flipr_id} {self.entity_description.name}"

    @property
    def native_value(self):
        """State of the sensor."""
        state = self.coordinator.data[self.entity_description.key]
        if isinstance(state, datetime):
            return state.isoformat()
        return state

    @property
    def device_class(self):
        """Return the device class."""
        return self.entity_description.device_class

    @property
    def icon(self):
        """Return the icon."""
        return self.entity_description.icon

    @property
    def native_unit_of_measurement(self):
        """Return unit of measurement."""
        return self.entity_description.native_unit_of_measurement
