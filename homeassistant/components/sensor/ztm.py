"""
Support for Zarząd Transportu Miejskiego w Warszawie (ZTM) transport data.

For more details about this platform please refer to the documentation at
https://home-assistant.io/components/sensor.ztm
"""
import asyncio
from datetime import datetime, timedelta
import logging
import aiohttp

import async_timeout
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_NAME, CONF_API_KEY, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = ("Data provided by Miasto Stołeczne Warszawa "
                    "http://api.um.warszawa.pl")
ZTM_ENDPOINT = "https://api.um.warszawa.pl/api/action/dbtimetable_get/"
ZTM_DATA_ID = 'e923fa0e-d96c-43f9-ae6e-60518c9f3238'

REQUEST_TIMEOUT = 5  # seconds
SCAN_INTERVAL = timedelta(minutes=1)
ICON = 'mdi:train'

DEFAULT_NAME = "ZTM"
SENSOR_NAME_FORMAT = "{} {} departures from {} {}"

CONF_LINE_NUMBER = 'number'
CONF_LINES = 'lines'
CONF_BUS_STOP_ID = 'bus_stop_id'
CONF_BUS_STOP_NUMBER = 'bus_stop_number'
CONF_ENTRIES = 'entries'
DEFAULT_ENTRIES = 3

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_LINES): [{
        vol.Required(CONF_LINE_NUMBER): cv.string,
        vol.Required(CONF_BUS_STOP_ID): cv.string,
        vol.Required(CONF_BUS_STOP_NUMBER): cv.string}],
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_ENTRIES, default=DEFAULT_ENTRIES): cv.positive_int,
    })


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the ZTM platform."""
    websession = async_get_clientsession(hass)
    api_key = config.get(CONF_API_KEY)
    name = config.get(CONF_NAME)
    entries = config.get(CONF_ENTRIES)
    lines = []
    for line_config in config.get(CONF_LINES):
        line = line_config.get(CONF_LINE_NUMBER)
        bus_stop_id = line_config.get(CONF_BUS_STOP_ID)
        bus_stop_number = line_config.get(CONF_BUS_STOP_NUMBER)
        sensor_name = SENSOR_NAME_FORMAT.format(name, line, bus_stop_id,
                                                bus_stop_number)
        lines.append(ZTMSensor(hass.loop, websession, api_key, line,
                               bus_stop_id, bus_stop_number, sensor_name,
                               entries))
    async_add_devices(lines)


class ZTMSensor(Entity):
    """Implementation of a ZTM sensor."""

    def __init__(self, loop, websession, api_key, line, bus_stop_id,
                 bus_stop_number, name, entries):
        """Initialize the sensor."""
        self._loop = loop
        self._websession = websession
        self._line = line
        self._bus_stop_id = bus_stop_id
        self._bus_stop_number = bus_stop_number
        self._name = name
        self._entries = entries
        self._state = STATE_UNKNOWN
        self._attributes = {'departures': []}
        self._unit = 'min'
        self._icon = ICON
        self._timetable = []
        self._timetable_date = None
        self._uri = ZTM_ENDPOINT
        self._params = {
            'id': ZTM_DATA_ID,
            'apikey': api_key,
            'busstopId': bus_stop_id,
            'busstopNr': bus_stop_number,
            'line': line,
        }

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
        """Return the unit of measurement."""
        return self._unit

    @property
    def device_state_attributes(self):
        """Return extra attributes."""
        self._attributes[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        return self._attributes

    @asyncio.coroutine
    def async_update(self):
        """Update state."""
        if self.data_is_outdated():
            res = yield from async_http_request(self._loop, self._websession,
                                                self._uri, self._params)
            if res.get('error', ''):
                self._state = "Error: {}".format(res['error'])
                self._unit = ''
            else:
                self._timetable = self.map_results(res.get('results', []))
                self._timetable_date = dt_util.now().date()
                _LOGGER.info("Downloaded timetable for line:%s stop:%s-%s",
                             self._line, self._bus_stop_id,
                             self._bus_stop_number)

        # check if there are trains after actual time
        departures = []
        now = dt_util.now()
        for entry in self._timetable:
            entry_dt = datetime.combine(now.date(),
                                        dt_util.parse_time(entry['czas']),
                                        now.tzinfo)
            if entry_dt > now:
                time_left = int((entry_dt - now).seconds / 60)
                departures.append(time_left)
                if len(departures) == self._entries:
                    break
        if departures:
            self._state = departures[0]
            self._attributes['departures'] = departures
            self._unit = 'min'
        else:
            self._state = STATE_UNKNOWN
            self._unit = ''

    def data_is_outdated(self):
        """Check if the internal sensor data is outdated."""
        now = dt_util.now()
        return self._timetable_date != now.date()

    @staticmethod
    def map_results(response):
        """Map all timetable entries to proper {'key': 'value'} struct."""
        return [parse_raw_timetable(row) for row in response['result']]


def parse_raw_timetable(raw_result):
    """Change {'key': 'name','value': 'val'} into {'name': 'val'}."""
    result = {}
    for val in raw_result.get('values', []):
        result[val['key']] = val['value']
    return result


@asyncio.coroutine
def async_http_request(loop, websession, uri, params):
    """Perform actual request."""
    try:
        with async_timeout.timeout(REQUEST_TIMEOUT, loop=loop):
            req = yield from websession.get(uri, params=params)
        if req.status != 200:
            return {'error': req.status}
        json_response = yield from req.json()
        return {'results': json_response}
    except (asyncio.TimeoutError, aiohttp.ClientError):
        _LOGGER.error("Cannot connect to ZTM API endpoint.")
    except ValueError:
        _LOGGER.error("Received non-JSON data from ZTM API endpoint")
