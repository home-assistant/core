"""
Support for Ebusd daemon for communication with eBUS heating systems.

For more details about ebusd deamon, please refer to the documentation at
https://github.com/john30/ebusd
"""

import logging

from homeassistant.const import (
    STATE_ON, STATE_OFF)
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['ebusd']

DATA_EBUSD = 'EBUSD'

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Ebus sensor."""
    ebusd_api = hass.data[DATA_EBUSD]
    monitored_conditions = discovery_info['monitored_conditions']
    name = discovery_info['client_name']

    dev = []
    for condition in monitored_conditions:
        dev.append(Ebusd(
            ebusd_api, discovery_info['sensor_types'][condition], name))

    add_entities(dev, True)


class Ebusd(Entity):
    """Representation of a Sensor."""

    def __init__(self, data, sensor, name):
        """Initialize the sensor."""
        self._state = None
        self._client_name = name
        self._name = sensor[0]
        self._unit_of_measurement = sensor[1]
        self._icon = sensor[2]
        self._type = sensor[3]
        self.data = data

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    def update(self):
        """Fetch new state data for the sensor."""
        try:
            self.data.update(self._name)
            if self._name not in self.data.value:
                return

            self._state = self.data.value[self._name]
        except RuntimeError:
            _LOGGER.debug("EbusdData.update exception")
