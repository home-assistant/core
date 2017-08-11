"""
Support for Fronius Symo Inverters with solar panels.

This component is based on the REST component
https://home-assistant.io/components/sensor.rest/

Example configuration:
sensor:
    - fronius_symo
      resource: 192.168.1.27 # The local IP of your Fronius Symo
      name: "Fronius Symo Solar Adapter"
"""
import logging
import json
import requests

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_RESOURCE, STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_METHOD = 'GET'
DEFAULT_NAME = 'Fronius Solar'
DEFAULT_VERIFY_SSL = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCE): cv.url,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Fronius Symo sensor."""
    name = config.get(CONF_NAME)
    resource = config.get(CONF_RESOURCE)

    # add fronius solar json path to resource
    fronius_solar_json_path = "solar_api/v1/GetInverterRealtimeData.fcgi?Scope=System"
    if(resource[-1] != '/'):
        fronius_solar_json_path = "/" + fronius_solar_json_path
    resource = resource + fronius_solar_json_path

    method = DEFAULT_METHOD
    auth = None
    headers = None
    payload = None
    verify_ssl = DEFAULT_VERIFY_SSL
    rest = JSONRestData(method, resource, auth, headers, payload, verify_ssl)
    rest.update()

    if rest.data is None:
        _LOGGER.error("Unable to fetch Fronius data")
        return False

    add_devices([FroniusSymoSolar(hass, rest, name)])


class FroniusSymoSolar(Entity):
    """Implementation of the Fronius Symo sensor."""

    def __init__(self, hass, rest, name):
        """Initialize the Fronius Symo sensor."""
        self._hass = hass
        self.rest = rest
        self._name = name
        self._attributes = []
        self._state = STATE_UNKNOWN
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Get the latest data from REST API and update the state."""
        self.rest.update()
        value = self.rest.data

        if value is None:
            value = STATE_UNKNOWN

        self._state = value

        # Parse the return text as JSON and save the json as an attribute.
        try:
            json_dict = json.loads(value)
            # Create a single sensor for every transmitted value
            # list of transmitted values
            trans_values = [
                {
                    'id': 'current_production',
                    'value':
                        json_dict['Body']['Data']['PAC']['Values']['1'],
                    'attributes':
                        {
                            'friendly_name': 'Current solar production',
                            'unit_of_measurement':
                                json_dict['Body']['Data']['PAC']['Unit'],
                            'icon': 'mdi:weather-sunny'
                        }
                },
                {
                    'id': 'day_production',
                    'value':
                        json_dict['Body']['Data']['DAY_ENERGY']['Values']['1'],
                    'attributes':
                        {
                            'friendly_name': 'Solar production of the day',
                            'unit_of_measurement':
                                json_dict['Body']['Data']['DAY_ENERGY']['Unit'],
                            'icon': 'mdi:weather-sunny'
                        }
                },
                {
                    'id': 'year_production',
                    'value':
                        json_dict['Body']['Data']['YEAR_ENERGY']['Values']['1'] / 1000,
                    'attributes':
                    {
                        'friendly_name': 'Solar production of the year',
                        'unit_of_measurement':
                            'k' + json_dict['Body']['Data']['YEAR_ENERGY']['Unit'],
                        'icon': 'mdi:weather-sunny'
                    }
                },
                {
                    'id': 'total_production',
                    'value':
                        json_dict['Body']['Data']['TOTAL_ENERGY']['Values']['1'] / 1000000,
                    'attributes':
                    {
                        'friendly_name': 'Total solar production ',
                        'unit_of_measurement':
                            'M' + json_dict['Body']['Data']['TOTAL_ENERGY']['Unit'],
                        'icon': 'mdi:weather-sunny'
                    }
                }
            ]

            # collect them in a list to create a group containing them later
            sensor_list = []

            # Iterate over all sensors
            for sensor in trans_values:
                entity_id = 'sensor.fronius_symo_solar_'+sensor['id']

                # do the adding
                self._hass.states.set(
                    entity_id,
                    sensor['value'],
                    sensor['attributes']
                )
                sensor_list.append(entity_id)

            # create the group that sums up all sensors
            self._hass.states.set(
                'group.fronius_symo_solar',
                'Running',
                {
                    'entity_id': sensor_list,
                    'friendly_name': self._name,
                    'icon': 'mdi:weather-sunny'
                }
            )

            # take over the complete json value
            self._attributes = json_dict
            # and recommend yourself as hidden
            self._attributes['hidden'] = 'true'

        except ValueError:
            self._attributes = []

    @property
    def state_attributes(self):
        """Return the attributes of the entity.

           Provide the parsed JSON data (if any).
        """
        return self._attributes


class JSONRestData(object):
    """Class for handling the data retrieval."""

    def __init__(self, method, resource, auth, headers, data, verify_ssl):
        """Initialize the data object."""
        self._request = requests.Request(
            method, resource, headers=headers, auth=auth, data=data).prepare()
        self._verify_ssl = verify_ssl
        self.data = None

    def update(self):
        """Get the latest data from REST service with provided method."""
        try:
            with requests.Session() as sess:
                response = sess.send(
                    self._request, timeout=10, verify=self._verify_ssl)

            self.data = response.text
        except requests.exceptions.RequestException:
            _LOGGER.error("Error fetching data: %s", self._request)
            self.data = None
