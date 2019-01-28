"""
Support for Repetier-Server sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.repetier/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY,
    CONF_PORT,
    CONF_URL,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['pyrepetier==1.4.1']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)

DEFAULT_PORT = '3344'
DEFAULT_DECIMALS = 1
DEFAULT_STATEPCT = False

ICON = 'mdi:printer-3d'

CONF_DECIMAL_PLACES = 'decimals'
CONF_STATE_PERCENT = 'state_percent'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
    vol.Optional(CONF_DECIMAL_PLACES, default=DEFAULT_DECIMALS): int,
    vol.Optional(CONF_STATE_PERCENT, default=DEFAULT_STATEPCT): bool,
})


def parse_repetier_api_response(response):
    """Parse the Repetier Server API json response."""
    data_dict = {}

    i = 0
    for printer in response['data']:
        _key = i
        i += 1
        if _key not in data_dict.keys():
            data_dict[_key] = printer
        else:
            data_dict[_key].update(printer)
    return data_dict


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Repetier sensors."""
    import pyrepetier
    decimal_places = config.get(CONF_DECIMAL_PLACES)
    state_pct = config.get(CONF_STATE_PERCENT)

    data = pyrepetier.RepetierData(
        parse_repetier_api_response,
        url=config[CONF_URL],
        port=config.get(CONF_PORT),
        api_key=config[CONF_API_KEY])
    data.update()
    sensors = []
    for key in data.data.keys():
        sensors.append(RepetierSensor(state_pct, decimal_places, key, data))
    add_devices(sensors, True)


class RepetierSensor(Entity):
    """Class to hold Repetier Sensor basic info."""

    def __init__(self, state_pct, decimal_places, repetier_id, data):
        """Initialize the sensor object."""
        self._repetier_id = repetier_id
        self._data = data
        self._icon = ICON
        self._name = None
        self._state = None
        self._units = None
        self._attributes = None
        self._decimals = decimal_places
        self._show_pct = state_pct
        self.format_data()

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
        return self._icon

    @property
    def unit_of_measurement(self):
        """Set units of measurement."""
        return self._units

    @property
    def device_state_attributes(self):
        """Attributes."""
        return self._attributes

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Update the sensor."""
        try:
            self._data.update()
            self.format_data()
        except (RuntimeError, TypeError, NameError):
            _LOGGER.error("Error updating Repetier Server sensors")

    def format_data(self):
        """Format output data."""
        self._name = self._data.data[self._repetier_id]['name']

        if self._data.data[self._repetier_id]['online'] == 1:
            if self._data.data[self._repetier_id]['job'] != 'none':
                if self._show_pct:
                    self._state = round(
                        self._data.data[self._repetier_id]['done'],
                        self._decimals)
                    self._units = '%'
                else:
                    self._state = STATE_ON
                    self._units = None
                self._attributes = {
                    'active':
                        self._data.data[self._repetier_id]['active'],
                    'analysed':
                        self._data.data[self._repetier_id]['analysed'],
                    'done':
                        self._data.data[self._repetier_id]['done'],
                    'job':
                        self._data.data[self._repetier_id]['job'],
                    'jobid':
                        self._data.data[self._repetier_id]['jobid'],
                    'linesSend':
                        self._data.data[self._repetier_id]['linesSend'],
                    'ofLayer':
                        self._data.data[self._repetier_id]['ofLayer'],
                    'pauseState':
                        self._data.data[self._repetier_id]['pauseState'],
                    'paused':
                        self._data.data[self._repetier_id]['paused'],
                    'printTime':
                        self._data.data[self._repetier_id]['printTime'],
                    'printedTimeComp':
                        self._data.data[self._repetier_id]['printedTimeComp'],
                    'start':
                        self._data.data[self._repetier_id]['start'],
                    'totalLines':
                        self._data.data[self._repetier_id]['totalLines'],
                    'online':
                        self._data.data[self._repetier_id]['online'],
                }
            else:
                if self._show_pct:
                    self._state = STATE_IDLE
                else:
                    self._state = STATE_IDLE
                self._attributes = {
                    'active':
                        self._data.data[self._repetier_id]['active'],
                    'job':
                        self._data.data[self._repetier_id]['job'],
                    'pauseState':
                        self._data.data[self._repetier_id]['pauseState'],
                    'paused':
                        self._data.data[self._repetier_id]['paused'],
                    'online':
                        self._data.data[self._repetier_id]['online'],
                }
                self._units = None
        else:
            self._state = STATE_OFF
            self._attributes = {
                'active':
                    self._data.data[self._repetier_id]['active'],
                'job':
                    self._data.data[self._repetier_id]['job'],
                'pauseState':
                    self._data.data[self._repetier_id]['pauseState'],
                'paused':
                    self._data.data[self._repetier_id]['paused'],
                'online':
                    self._data.data[self._repetier_id]['online'],
            }
            self._units = None
