"""
Sensor for checking the status of London Underground tube lines.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.london_underground/
"""
import logging
from datetime import timedelta

import voluptuous as vol
import requests

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Powered by TfL Open Data"
CONF_LINE = 'line'
SCAN_INTERVAL = timedelta(seconds=30)
TUBE_LINES = [
    'Bakerloo',
    'Central',
    'Circle',
    'District',
    'DLR',
    'Hammersmith & City',
    'Jubilee',
    'London Overground',
    'Metropolitan',
    'Northern',
    'Piccadilly',
    'TfL Rail',
    'Victoria',
    'Waterloo & City']
URL = 'https://api.tfl.gov.uk/line/mode/tube,overground,dlr,tflrail/status'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_LINE):
        vol.All(cv.ensure_list, [vol.In(list(TUBE_LINES))]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Tube sensor."""
    data = TubeData()
    data.update()
    sensors = []
    for line in config.get(CONF_LINE):
        sensors.append(LondonTubeSensor(line, data))

    add_devices(sensors, True)


class LondonTubeSensor(Entity):
    """Sensor that reads the status of a line from TubeData."""

    ICON = 'mdi:subway'

    def __init__(self, name, data):
        """Initialize the sensor."""
        self._name = name
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
        attrs = {}
        attrs['Description'] = self._description
        return attrs

    def update(self):
        """Update the sensor."""
        self._data.update()
        self._state = self._data.data[self.name]['State']
        self._description = self._data.data[self.name]['Description']


class TubeData:
    """Get the latest tube data from TFL."""

    def __init__(self):
        """Initialize the TubeData object."""
        self.data = None

    # Update only once in scan interval.
    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Get the latest data from TFL."""
        response = requests.get(URL)
        if response.status_code != 200:
            _LOGGER.warning("Invalid response from API")
        else:
            self.data = parse_api_response(response.json())


def parse_api_response(response):
    """Take in the TFL API json response."""
    lines = [line['name'] for line in response]
    data_dict = dict.fromkeys(lines)

    for line in response:
        statuses = [status['statusSeverityDescription']
                    for status in line['lineStatuses']]
        state = ' + '.join(sorted(set(statuses)))

        if state == 'Good Service':
            reason = 'Nothing to report'
        else:
            reason = ' *** '.join(
                [status['reason'] for status in line['lineStatuses']])

        attr = {'State': state, 'Description': reason}
        data_dict[line['name']] = attr

    return data_dict
