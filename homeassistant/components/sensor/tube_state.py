"""
For more details about this component, please refer to the documentation at
To do
"""

import voluptuous as vol
import logging
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.util import Throttle

from datetime import datetime, timedelta
import requests
import json

SCAN_INTERVAL = timedelta(minutes=1)

DOMAIN = 'tube_state'     #  must match the name of the compoenent
CONF_LINE= 'line'
ATTRIBUTION = "Powered by TfL Open Data"
TUBE_LINES= ['Bakerloo',
             'Central',
             'Circle',
             'District',
             'Hammersmith & City',
             'Jubilee',
             'Metropolitan',
             'Northern',
             'Piccadilly',
             'Victoria',
             'Waterloo & City']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
      vol.Required(CONF_LINE): vol.In(TUBE_LINES)    # Check a valid line
    })
}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)      # enable logging to console


def setup_platform(hass, config, add_devices, discovery_info=None):

    data = TubeData()  # fetch the data dict
    data.update()      # Get the init data
    sensors = []
    for line in config.get(CONF_LINE):
        sensors.append(LondonTubeSensor(line, data))

    add_devices(sensors, True)
    _LOGGER.info("The tube_state component is ready!")
    _LOGGER.info(ATTRIBUTION)


class LondonTubeSensor(Entity):    # Entity
    """
    Sensor that reads the status of a line from TubeData.
    """

    ICON = 'mdi:subway'

    def __init__(self, name, data):
        """Initialize the sensor."""
        self._name = name             # the name of the line from the allowed list
        self._data = data
        self._state = None
        self._description = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self.ICON

    @property
    def device_state_attributes(self):
        """Return other details about the sensor state."""
        attrs = {}  # {'attribution': 'Data provided by transportapi.com'}
        attrs['Description'] = self._description # if there is data, append
        return attrs

    def update(self):
        """Update the sensor."""
        self._data.update()      # update the data object
        self._state = self._data.data[self.name]['State']
        self._description = self._data.data[self.name]['Description']


class TubeData(object):
    """Get the latest tube data from TFL."""

    def __init__(self):
        """Initialize the data object."""
        self.data = None

    @Throttle(SCAN_INTERVAL)  # update only once in scan interval
    def update(self):
        """Get the latest data from TFL."""
        URL = 'https://api.tfl.gov.uk/line/mode/tube/status'
        response = requests.get(URL)
        _LOGGER.info("TFL Request made")
        if response.status_code != 200:
            _LOGGER.warning("Invalid response from API")
            #print("Invalid response from API")
        else:
            self.data = parse_API_response(response.json())


def parse_API_response(response):
    '''Take in the TFL API json response to
       https://api.tfl.gov.uk/line/mode/tube/status'''
    lines = [line['name'] for line in response]    # All available lines
    data_dict = dict.fromkeys(lines)

    for line in response:                     # Assign data via key
        statuses = [status['statusSeverityDescription'] for status in line['lineStatuses']]
        state = ' + '.join(sorted(set(statuses)))

        if state == 'Good Service':   # if good status, this is the only status returned
            reason =  'Nothing to report'
        else:
            reason = ' *** '.join([status['reason'] for status in line['lineStatuses']])

        attr = {'State': state, 'Description': reason}
        data_dict[line['name']] = attr

    return data_dict
