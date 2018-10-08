"""
Support for monitoring OctoPrint binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.octoprint/
"""
import logging

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, ENTITY_ID_FORMAT, PLATFORM_SCHEMA)
from homeassistant.const import CONF_NAME, CONF_MONITORED_CONDITIONS
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['octoprint']
DOMAIN = "octoprint"
DEFAULT_NAME = 'octoprint'

SENSOR_TYPES = {
    # API Endpoint, Group, Key, unit
    'Printing': ['printer', 'state', 'printing', None],
    'Printing Error': ['printer', 'state', 'error', None]
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the available OctoPrint binary sensors."""
    name = config.get(CONF_NAME)

    if name in hass.data[DOMAIN]:
        octoprint_api = hass.data[DOMAIN][name]
        monitored_conditions = config.get(
            CONF_MONITORED_CONDITIONS, SENSOR_TYPES.keys())

        devices = []
        for octo_type in monitored_conditions:
            _LOGGER.debug(
                'Setting up Octoprint {} binary sensor {}'.format(
                    name,
                    octo_type
                )
            )
            new_sensor = OctoPrintBinarySensor(
                octoprint_api,
                octo_type, SENSOR_TYPES[octo_type][2],
                SENSOR_TYPES[octo_type][3],
                SENSOR_TYPES[octo_type][0],
                SENSOR_TYPES[octo_type][1],
                'flags'
            )
            devices.append(new_sensor)
        add_entities(devices, True)
    else:
        _LOGGER.error(
            'Unable to setup binary sensors'
            'due to Octoprint {} not found'.format(name)
        )


class OctoPrintBinarySensor(BinarySensorDevice):
    """Representation an OctoPrint binary sensor."""

    def __init__(self, api, condition, sensor_type, unit,
                 endpoint, group, tool=None):
        """Initialize a new OctoPrint sensor."""
        self.sensor_name = api.name
        if tool is None:
            self._name = '{} {}'.format(self.sensor_name, condition)
            self.entity_id = ENTITY_ID_FORMAT.format(slugify(self._name))
        else:
            self._name = '{} {}'.format(self.sensor_name, condition)
            self.entity_id = ENTITY_ID_FORMAT.format(slugify(self._name))
        self.friendly_name = '{} - {}'.format(self.sensor_name, condition)
        self.sensor_type = sensor_type
        self.api = api
        self._state = False
        self._unit_of_measurement = unit
        self.api_endpoint = endpoint
        self.api_group = group
        self.api_tool = tool
        _LOGGER.debug("Created OctoPrint binary sensor %r", self)

    @property
    def name(self):
        """Return the name of the sensor."""
        if self.friendly_name:
            name = self.friendly_name.title()
        else:
            name = self._name
        return name

    @property
    def is_on(self):
        """Return true if binary sensor is on."""
        return bool(self._state)

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return None

    def update(self):
        """Update state of sensor."""
        try:
            self._state = self.api.update(
                self.sensor_type, self.api_endpoint, self.api_group,
                self.api_tool)
        except requests.exceptions.ConnectionError:
            # Error calling the api, already logged in api.update()
            return
