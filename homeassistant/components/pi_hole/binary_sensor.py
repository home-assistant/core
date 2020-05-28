"""Support for getting statistical data from a Pi-hole system."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_NAME

from .const import (
    BINARY_SENSOR_DICT,
    BINARY_SENSOR_LIST,
    DOMAIN as PIHOLE_DOMAIN,
    STATUS_ENABLED,
)

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the pi-hole sensor."""
    pi_hole = hass.data[PIHOLE_DOMAIN][entry.data[CONF_NAME]]
    sensors = [
        PiHoleBinarySensor(pi_hole, sensor_name, entry.entry_id)
        for sensor_name in BINARY_SENSOR_LIST
    ]
    async_add_entities(sensors, True)


class PiHoleBinarySensor(BinarySensorEntity):
    """Representation of a Pi-hole binary sensor."""

    def __init__(self, pi_hole, sensor_name, server_unique_id):
        """Initialize a Pi-hole sensor."""
        LOGGER.debug("Setting up pi-hole binary sensor %s", sensor_name)
        self.pi_hole = pi_hole
        self._name = pi_hole.name
        self._condition = sensor_name
        self._server_unique_id = server_unique_id

        variable_info = BINARY_SENSOR_DICT[sensor_name]
        self._condition_name = variable_info[0]
        self._condition = variable_info[1]
        self._on_value = variable_info[2]
        self._device_class = variable_info[3]
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
    def device_class(self):
        """Icon to use in the frontend, if any."""
        return self._device_class

    @property
    def is_on(self):
        """Return the state of the device."""
        LOGGER.debug("Condition: %s", self._condition)
        # return self.data[self._condition] == self._on_value
        return self.data["status"] == STATUS_ENABLED

    @property
    def device_state_attributes(self):
        """Return the state attributes of the Pi-Hole."""
        return self.data

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self.pi_hole.available

    async def async_update(self):
        """Get the latest data from the Pi-hole API."""
        LOGGER.debug("Getting updates for pihole binary sensor")
        await self.pi_hole.async_update()
        self.data = self.pi_hole.api.data
