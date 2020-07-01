"""Sensor platform for the PoolSense sensor."""
import logging

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    STATE_OK,
    STATE_PROBLEM,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)
from homeassistant.helpers.entity import Entity

from . import get_coordinator
from .const import ATTRIBUTION

_LOGGER = logging.getLogger(__name__)

SENSORS = {
    "Chlorine": {
        "unit": "mV",
        "icon": "mdi:pool",
        "name": "Chlorine",
        "device_class": None,
    },
    "pH": {"unit": None, "icon": "mdi:pool", "name": "pH", "device_class": None},
    "Battery": {
        "unit": UNIT_PERCENTAGE,
        "icon": "mdi:battery",
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
    "pH Status": {
        "unit": None,
        "icon": "mdi:pool",
        "name": "pH Status",
        "device_class": None,
    },
    "Chlorine Status": {
        "unit": None,
        "icon": "mdi:pool",
        "name": "Chlorine Status",
        "device_class": None,
    },
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer sensor setup to the shared sensor module."""
    coordinator = await get_coordinator(hass, config_entry)

    async_add_entities(
        PoolSenseSensor(
            coordinator,
            config_entry.data["email"],
            config_entry.data["password"],
            info_type,
        )
        for info_type in SENSORS
    )


class PoolSenseSensor(Entity):
    """Sensor representing poolsense data."""

    unique_id = None

    def __init__(self, coordinator, email, password, info_type):
        """Initialize poolsense sensor."""
        self._email = email
        self._password = password
        self.unique_id = f"{email}-{info_type}"
        self.coordinator = coordinator
        self.info_type = info_type

    @property
    def available(self):
        """Return if sensor is available."""
        return self.coordinator.last_update_success

    @property
    def name(self):
        """Return the name of the particular component."""
        return "PoolSense {}".format(SENSORS[self.info_type]["name"])

    @property
    def state(self):
        """State of the sensor."""
        if self.info_type == "pH Status":
            if self.coordinator.data[self.info_type] == "red":
                return STATE_PROBLEM
            return STATE_OK
        if self.info_type == "Chlorine Status":
            if self.coordinator.data[self.info_type] == "red":
                return STATE_PROBLEM
            return STATE_OK
        return self.coordinator.data[self.info_type]

    @property
    def device_class(self):
        """Return the device class."""
        return SENSORS[self.info_type]["device_class"]

    @property
    def icon(self):
        """Return the icon."""
        if self.info_type == "pH Status":
            if self.coordinator.data[self.info_type] == "red":
                return "mdi:thumb-down"
            return "mdi:thumb-up"
        if self.info_type == "Chlorine Status":
            if self.coordinator.data[self.info_type] == "red":
                return "mdi:thumb-down"
            return "mdi:thumb-up"
        return SENSORS[self.info_type]["icon"]

    @property
    def unit_of_measurement(self):
        """Return unit of measurement."""
        return SENSORS[self.info_type]["unit"]

    @property
    def device_state_attributes(self):
        """Return device attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
