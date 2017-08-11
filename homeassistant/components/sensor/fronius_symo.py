"""
Support for Fronius Symo Inverters.

This component is based on the REST component
https://home-assistant.io/components/sensor.rest/

Example configuration:
sensor:
    - fronius_symo
      resource: 192.168.1.27 # The local IP of your Fronius Symo
      name: "Fronius Grid"

"""
import logging

import voluptuous as vol
import json
import requests

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_RESOURCE)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_METHOD = 'GET'
DEFAULT_NAME = 'Fronius Grid'
DEFAULT_VERIFY_SSL = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCE): cv.url,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Set up the Fronius Symo sensor."""
    name = config.get(CONF_NAME)
    resource = config.get(CONF_RESOURCE)

    # add fronius solar json path to resource
    fronius_grid_json_path = "components/5/0/?print=names"
    if resource[-1] != '/':
        fronius_grid_json_path = "/" + fronius_grid_json_path
    resource = resource + fronius_grid_json_path

    method = DEFAULT_METHOD
    payload = None
    verify_ssl = DEFAULT_VERIFY_SSL
    headers = None

    auth = None
    rest = JSONRestData(method, resource, auth, headers, payload, verify_ssl)
    rest.update()

    if rest.data is None:
        _LOGGER.error("Unable to fetch Fronius data")
        return False

    add_devices([FroniusSensor(hass, rest, name)])


class FroniusSensor(Entity):
    """Implementation of the Fronius sensor."""

    def __init__(self, hass, rest, name):
        """Initialize the Fronius sensor."""
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
        """Get the latest data from Fronius Symo and update the state."""
        self.rest.update()
        value = self.rest.data

        if value is None:
            value = STATE_UNKNOWN

        self._state = value
    
        # Parse the return text as JSON and save the json as an attribute.
        try:
            json_dict = json.loads(value)
            # Create a single sensor for every transmitted value
            
            # the list of transmitted values
            trans_values = [
                {
                    'id': 'current_generated_power',
                    'value':
                        json_dict['Body']['Data']['Power_P_Generate']['value'],
                    'attributes':
                    {
                        'friendly_name': 'Currently generated power',
                        'unit_of_measurement':
                            json_dict['Body']['Data']['Power_P_Generate']['unit'],
                        'icon': 'mdi:power-plug'
                    }
                },
                {
                    'id': 'current_load',
                    'value':
                        json_dict['Body']['Data']['Power_P_Load']['value'],
                    'attributes':
                    {
                        'friendly_name': 'Current load',
                        'unit_of_measurement':
                            json_dict['Body']['Data']['Power_P_Load']['unit'],
                        'icon': 'mdi:power-plug'
                    }
                },
                {
                    'id': 'current_grid_consumption',
                    'value': 
                        json_dict['Body']['Data']['Power_P_Grid']['value'],
                    'attributes':
                    {
                        'friendly_name': 'Current grid consumption',
                        'unit_of_measurement':
                            json_dict['Body']['Data']['Power_P_Grid']['unit'],
                        'icon': 'mdi:power-plug'
                    }
                },
                {
                    'id': 'current_akku_sum',
                    'value':
                        json_dict['Body']['Data']['Power_Akku_Sum']['value'],
                    'attributes':
                    {
                        'friendly_name': 'Current battery use',
                        'unit_of_measurement':
                            json_dict['Body']['Data']['Power_Akku_Sum']['unit'],
                        'icon': 'mdi:battery'
                    }
                },
                {
                    'id': 'current_pv_sum',
                    'value':
                        json_dict['Body']['Data']['Power_PV_Sum']['value'],
                    'attributes':
                    {
                        'friendly_name': 'Current PV use',
                        'unit_of_measurement':
                            json_dict['Body']['Data']['Power_PV_Sum']['unit'],
                        'icon': 'mdi:power-plug'
                    }
                },
                {
                    'id': 'current_self_consumption',
                    'value':
                        json_dict['Body']['Data']['Power_P_SelfConsumption']['value'],
                    'attributes':
                    {
                        'friendly_name': 'Current self consumption',
                        'unit_of_measurement':
                            json_dict['Body']['Data']['Power_P_SelfConsumption']['unit'],
                        'icon': 'mdi:power-plug'
                    }
                },
                {
                    'id': 'current_relative_self_consumption',
                    'value':
                        json_dict['Body']['Data']['Relative_Current_SelfConsumption']['value'],
                    'attributes':
                    {
                        'friendly_name': 'Current relative self consumption',
                        'unit_of_measurement':
                            json_dict['Body']['Data']['Relative_Current_SelfConsumption']['unit'],
                        'icon': 'mdi:power-plug'
                    }
                },
                {
                    'id': 'current_autonomy',
                    'value':
                        json_dict['Body']['Data']['Relative_Current_Autonomy']['value'],
                    'attributes':
                    {
                        'friendly_name': 'Current autonomy',
                        'unit_of_measurement':
                            json_dict['Body']['Data']['Relative_Current_Autonomy']['unit'],
                        'icon': 'mdi:weather-sunny'
                    }
                },
            ]

            # Collect them in a list to create a group containing them later
            sensor_list = []

            # Iterate over all sensors
            for sensor in trans_values:
                value = sensor['value']
                # handle null values
                """
                self consumption is null when generated power is null,
                so it should actually be equal to current grid / at 100%
                """
                if value == 'null' or value is None:
                    if sensor['id'] == 'current_self_consumption':
                        # absolute self consumption = grid(2)"""
                        value = trans_values[2]['value']
                    elif sensor['id'] == 'current_relative_self_consumption':
                        # relative self consumption at 100
                        value = 100
                    else:
                        # every other value is 0 when null
                        value = 0

                entity_id = 'sensor.fronius_symo_'+sensor['id']

                # do the adding
                self._hass.states.set(entity_id, value, sensor['attributes'])
                sensor_list.append(entity_id)

            # create the group that sums up all sensors
            self._hass.states.set(
                'group.fronius_symo',
                'Running',
                {
                    'entity_id': sensor_list,
                    'friendly_name': self._name,
                    'icon': 'mdi:power-plug'
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
