"""Sensor platform for the PoolSense sensor."""
import logging

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_EMAIL,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    STATE_OK,
    STATE_PROBLEM,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)
from homeassistant.helpers.entity import Entity

from .const import ATTRIBUTION, DOMAIN

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
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        PoolSenseSensor(coordinator, config_entry.data[CONF_EMAIL], info_type)
        for info_type in SENSORS
    )


class PoolSenseSensor(Entity):
    """Sensor representing poolsense data."""

    def __init__(self, coordinator, email, info_type):
        """Initialize poolsense sensor."""
        self._email = email
        self._unique_id = f"{email}-{info_type}"
        self.coordinator = coordinator
        self.info_type = info_type

    @property
    def available(self):
        """Return if sensor is available."""
        return self.coordinator.last_update_success

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the particular component."""
        return f"PoolSense {SENSORS[self.info_type]['name']}"

    @property
    def should_poll(self):
        """Return False, updates are controlled via coordinator."""
        return False

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

    async def async_update(self):
        """Update status of sensor."""
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
