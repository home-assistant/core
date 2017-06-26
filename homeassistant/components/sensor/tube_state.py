"""
For more details about this component, please refer to the documentation at
To do
"""

import voluptuous as vol
import logging
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.const import ATTR_ATTRIBUTION

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
             'Hammersmith-city',
             'Jubilee',
             'Metropolitan',
             'Northern',
             'Piccadilly',
             'Victoria',
             'Waterloo-city']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
      vol.Required(CONF_LINE): vol.In(TUBE_LINES)    # Check a valid line
    })
}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)      # enable logging to console


def setup_platform(hass, config, add_devices, discovery_info=None):
    sensors = []
    for tube in config.get(CONF_LINE):
        sensors.append(LondonTubeSensor(tube))

    add_devices(sensors)
    _LOGGER.info("The tube_state component is ready!")
    _LOGGER.info(ATTRIBUTION)


class LondonTubeSensor(Entity):    # Entity
    """
    Sensor that reads the status of a tube lines using the TFL API.
    """
    API_URL_BASE = "https://api.tfl.gov.uk/line/{}/status"
    ICON = 'mdi:subway'

    def __init__(self, name):
        """Initialize the sensor."""
        self._name = name             # the name of the line
        self._data = {}
        self._url = self.API_URL_BASE
        self._state = 'Updating'
        self._description = ['Updating']

    @property
    def name(self):
        """Return the line name of the sensor."""
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
        """Perform an API request and update the sensor."""
        response = requests.get(self._url.format(self._name.lower()))

        if response.status_code != 200:
            _LOGGER.warning("Invalid response from API")

        else:
            self._data = response.json()[0]['lineStatuses']
            statuses = [status['statusSeverityDescription']
                        for status in self._data] # get all statuses on a line

            if 'Good Service' in statuses:
                self._state = 'Good Service'
                self._description = 'Nothing to report'
            else:
                self._state = ' + '.join(sorted(set(statuses)))
                self._description = [status['reason'] for status
                                     in self._data] # get the reasons
