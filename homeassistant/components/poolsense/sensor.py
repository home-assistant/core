"""Sensor platform for the PoolSense sensor."""
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_EMAIL,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.helpers.entity import Entity

from . import PoolSenseEntity
from .const import ATTRIBUTION, DOMAIN

SENSORS = {
    "Chlorine": {
        "unit": "mV",
        "icon": "mdi:pool",
        "name": "Chlorine",
        "device_class": None,
    },
    "pH": {"unit": None, "icon": "mdi:pool", "name": "pH", "device_class": None},
    "Battery": {
        "unit": PERCENTAGE,
        "icon": None,
        "name": "Battery",
        "device_class": DEVICE_CLASS_BATTERY,
    },
    "Water Temp": {
        "unit": TEMP_CELSIUS,
        "icon": "mdi:coolant-temperature",
        "name": "Temperature",
        "device_class": DEVICE_CLASS_TEMPERATURE,
    },
    "Last Seen": {
        "unit": None,
        "icon": "mdi:clock",
        "name": "Last Seen",
        "device_class": DEVICE_CLASS_TIMESTAMP,
    },
    "Chlorine High": {
        "unit": "mV",
        "icon": "mdi:pool",
        "name": "Chlorine High",
        "device_class": None,
    },
    "Chlorine Low": {
        "unit": "mV",
        "icon": "mdi:pool",
        "name": "Chlorine Low",
        "device_class": None,
    },
    "pH High": {
        "unit": None,
        "icon": "mdi:pool",
        "name": "pH High",
        "device_class": None,
    },
    "pH Low": {
        "unit": None,
        "icon": "mdi:pool",
        "name": "pH Low",
        "device_class": None,
    },
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer sensor setup to the shared sensor module."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    sensors_list = []
    for sensor in SENSORS:
        sensors_list.append(
            PoolSenseSensor(coordinator, config_entry.data[CONF_EMAIL], sensor)
        )

    async_add_entities(sensors_list, False)


class PoolSenseSensor(PoolSenseEntity, Entity):
    """Sensor representing poolsense data."""

    @property
    def name(self):
        """Return the name of the particular component."""
        return f"PoolSense {SENSORS[self.info_type]['name']}"

    @property
    def state(self):
        """State of the sensor."""
        return self.coordinator.data[self.info_type]

    @property
    def device_class(self):
        """Return the device class."""
        return SENSORS[self.info_type]["device_class"]

    @property
    def icon(self):
        """Return the icon."""
        return SENSORS[self.info_type]["icon"]

    @property
    def unit_of_measurement(self):
        """Return unit of measurement."""
        return SENSORS[self.info_type]["unit"]

    @property
    def device_state_attributes(self):
        """Return device attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}
