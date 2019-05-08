"""Support for monitoring OctoPrint binary sensors."""
import logging

import requests

from homeassistant.components.binary_sensor import BinarySensorDevice

from . import BINARY_SENSOR_TYPES, DOMAIN as COMPONENT_DOMAIN

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the available OctoPrint binary sensors."""
    if discovery_info is None:
        return

    name = discovery_info['name']
    base_url = discovery_info['base_url']
    monitored_conditions = discovery_info['sensors']
    octoprint_api = hass.data[COMPONENT_DOMAIN][base_url]

    devices = []
    for octo_type in monitored_conditions:
        devices.append(OctoPrintBinarySensor(
            '{} {}'.format(name, octo_type), octoprint_api,
            BINARY_SENSOR_TYPES[octo_type][0],
            BINARY_SENSOR_TYPES[octo_type][1],
            BINARY_SENSOR_TYPES[octo_type][2]))
    add_entities(devices, True)


class OctoPrintBinarySensor(BinarySensorDevice):
    """Representation an OctoPrint binary sensor."""

    def __init__(self, name, api, endpoint, path, device_class=None):
        """Initialize a new OctoPrint sensor."""
        self._name = name
        self._state = None
        self._device_class = device_class
        self.api = api
        self.api_endpoint = endpoint
        self.api_path = path
        _LOGGER.debug("Created OctoPrint binary sensor %r", self)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if binary sensor is on."""
        return bool(self._state)

    @property
    def device_class(self):
        """Return the class of this binary sensor."""
        return self._device_class

    def update(self):
        """Update state of the binary sensor."""
        try:
            self._state = self.api.update(self.api_endpoint, self.api_path)
        except requests.exceptions.ConnectionError:
            # Error calling the api, already logged in api.update()
            return
