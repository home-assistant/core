"""Support for getting statistical data from a Pi-hole system."""
import logging

from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_BLOCKED_DOMAINS,
    DOMAIN as PIHOLE_DOMAIN,
    SENSOR_DICT,
    SENSOR_LIST,
)

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the pi-hole sensor."""
    pi_hole = hass.data[PIHOLE_DOMAIN][entry.data[CONF_NAME]]
    sensors = [
        PiHoleSensor(pi_hole, sensor_name, entry.entry_id)
        for sensor_name in SENSOR_LIST
    ]
    async_add_entities(sensors, True)


class PiHoleSensor(Entity):
    """Representation of a Pi-hole sensor."""

    def __init__(self, pi_hole, sensor_name, server_unique_id):
        """Initialize a Pi-hole sensor."""
        self.pi_hole = pi_hole
        self._name = pi_hole.name
        self._condition = sensor_name
        self._server_unique_id = server_unique_id

        variable_info = SENSOR_DICT[sensor_name]
        self._condition_name = variable_info[0]
        self._unit_of_measurement = variable_info[1]
        self._icon = variable_info[2]
        self.data = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {self._condition_name}"

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"{self._server_unique_id}/{self._condition_name}"

    @property
    def device_info(self):
        """Return the device information of the sensor."""
        return {
            "identifiers": {(PIHOLE_DOMAIN, self._server_unique_id)},
            "name": self._name,
            "manufacturer": "Pi-hole",
        }

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the device."""
        try:
            return round(self.data[self._condition], 2)
        except TypeError:
            return self.data[self._condition]

    @property
    def device_state_attributes(self):
        """Return the state attributes of the Pi-Hole."""
        return {ATTR_BLOCKED_DOMAINS: self.data["domains_being_blocked"]}

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self.pi_hole.available

    async def async_update(self):
        """Get the latest data from the Pi-hole API."""
        await self.pi_hole.async_update()
        self.data = self.pi_hole.api.data
