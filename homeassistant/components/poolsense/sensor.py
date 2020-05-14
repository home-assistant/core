"""Sensor platform for the PoolSense sensor."""
import logging

from homeassistant.const import ATTR_ATTRIBUTION, STATE_OK, STATE_PROBLEM
from homeassistant.helpers.entity import Entity

from . import get_coordinator
from .const import ATTRIBUTION

_LOGGER = logging.getLogger(__name__)

SENSORS = {
    "Chlorine": {"unit": "mV", "icon": "mdi:pool", "name": "Chlorine"},
    "pH": {"unit": "", "icon": "mdi:pool", "name": "pH"},
    "Battery": {"unit": "%", "icon": "mdi:battery", "name": "Battery"},
    "Water Temp": {
        "unit": "°C",
        "icon": "mdi:coolant-temperature",
        "name": "Temperature",
    },
    "Last Seen": {"unit": "", "icon": "mdi:clock", "name": "Last Seen"},
    "Chlorine High": {"unit": "mV", "icon": "mdi:pool", "name": "Chlorine High"},
    "Chlorine Low": {"unit": "mV", "icon": "mdi:pool", "name": "Chlorine Low"},
    "pH High": {"unit": "", "icon": "mdi:pool", "name": "pH High"},
    "pH Low": {"unit": "", "icon": "mdi:pool", "name": "pH Low"},
    "pH Status": {"unit": "", "icon": "mdi:pool", "name": "pH Status"},
    "Chlorine Status": {"unit": "", "icon": "mdi:pool", "name": "Chlorine Status"},
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
                return "!"
            return "✅"
        if self.info_type == "Chlorine Status":
            if self.coordinator.data[self.info_type] == "red":
                return "!"
            return "✅"
        return self.coordinator.data[self.info_type]

    @property
    def icon(self):
        """Return the icon."""
        if self.info_type == "pH Status":
            if self.coordinator.data[self.info_type] == "red":
                return "mda: thumb-down"
            return "mda: thumb-up"
        if self.info_type == "Chlorine Status":
            if self.coordinator.data[self.info_type] == "red":
                return "mda: thumb-down"
            return "mda: thumb-up"
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
        self.coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """When entity will be removed from hass."""
        self.coordinator.async_remove_listener(self.async_write_ha_state)
