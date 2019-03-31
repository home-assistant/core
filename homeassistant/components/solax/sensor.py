"""Support for Solax inverter via local API."""
import asyncio

from datetime import timedelta
import logging

import aiohttp
import json
import async_timeout
import voluptuous as vol

from homeassistant.const import (
        TEMP_CELSIUS,
        CONF_IP_ADDRESS
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

# key: name of sensor
# value.0: index
# value.1: unit (String) or None
# from https://github.com/GitHobi/solax/wiki/direct-data-retrieval
INVERTER_SENSORS = {
    'PV1 Current':                (0, 'A'),
    'PV2 Current':                (1, 'A'),
    'PV1 Voltage':                (2, 'V'),
    'PV2 Voltage':                (3, 'V'),

    'Output Current':             (4, 'A'),
    'Network Voltage':            (5, 'V'),
    'Power Now':                  (6, 'W'),

    'Inverter Temperature':       (7, TEMP_CELSIUS),
    'Today\'s Energy':            (8, 'kWh'),
    'Total Energy':               (9, 'kWh'),
    'Exported Power':             (10, 'W'),
    'PV1 Power':                  (11, 'W'),
    'PV2 Power':                  (12, 'W'),

    'Battery Voltage':            (13, 'V'),
    'Battery Current':            (14, 'A'),
    'Battery Power':              (15, 'W'),
    'Battery Temperature':        (16, TEMP_CELSIUS),
    'Battery Remaining Capacity': (17, '%'),

    'Battery Energy':             (19, 'kWh'),

    'Grid Frequency':             (50, 'Hz'),
    'EPS Voltage':                (53, 'V'),
    'EPS Current':                (54, 'A'),
    'EPS Power':                  (55, 'W'),
    'EPS Frequency':              (56, 'Hz'),
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_IP_ADDRESS): cv.string,
})

SCAN_INTERVAL = timedelta(seconds=30)
REQUEST_TIMEOUT = 5

REAL_TIME_DATA_ENDPOINT = 'http://{ip_address}/api/realTimeData.htm'

DATA_SCHEMA = vol.Schema(
    vol.All([vol.Coerce(float)], vol.Length(min=68, max=68))
)

REAL_TIME_DATA_SCHEMA = vol.Schema({
    vol.Required('method'): cv.string,
    vol.Required('version'): cv.string,
    vol.Required('type'): cv.string,
    vol.Required('SN'): cv.string,
    vol.Required('Data'): DATA_SCHEMA,
    vol.Required('Status'): cv.positive_int,
}, extra=vol.REMOVE_EXTRA)


class SolaxRequestError(Exception):
    """Error to indicate a Solax API request has failed."""
    pass


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Setup the sensor platform."""
    endpoint = RealTimeDataEndpoint(hass, config.get(CONF_IP_ADDRESS))
    hass.async_add_job(endpoint.async_refresh)
    async_track_time_interval(hass, endpoint.async_refresh, SCAN_INTERVAL)
    devices = []
    for x in INVERTER_SENSORS:
        devices.append(Inverter(x))
    endpoint.sensors = devices
    async_add_entities(devices)


async def async_solax_real_time_request(hass, schema, ip, retry, t_wait=0):
    if t_wait > 0:
        msg = "Timeout connecting to Solax inverter, waiting %d to retry."
        _LOGGER.warn(msg, t_wait)
        asyncio.sleep(t_wait)
    new_wait = (t_wait*2)+5
    retry = retry - 1
    try:
        session = async_get_clientsession(hass)

        with async_timeout.timeout(REQUEST_TIMEOUT, loop=hass.loop):
            url = REAL_TIME_DATA_ENDPOINT.format(ip_address=ip)
            req = await session.get(url)
        garbage = await req.read()
        formatted = garbage.decode("utf-8")
        formatted = formatted.replace(",,", ",0.0,").replace(",,", ",0.0,")
        json_response = json.loads(formatted)
        return schema(json_response)
    except (asyncio.TimeoutError):
        if retry > 0:
            return await async_solax_real_time_request(hass,
                                                       schema,
                                                       ip,
                                                       retry,
                                                       new_wait)
        _LOGGER.error("Too many timeouts connecting to Solax.")
    except (aiohttp.ClientError) as clientErr:
        _LOGGER.error("Could not connect to Solax API endpoint")
        _LOGGER.error(clientErr)
    except ValueError:
        _LOGGER.error("Received non-JSON data from Solax API endpoint")
    except vol.Invalid as err:
        _LOGGER.error("Received unexpected JSON from Solax"
                      " API endpoint: %s", err)
        _LOGGER.error(json_response)
    raise SolaxRequestError


def parse_solax_battery_response(json):
    data_list = json['Data']
    result = {}
    for k, v in INVERTER_SENSORS.items():
        response_index = v[0]
        result[k] = data_list[response_index]
    return result


class RealTimeDataEndpoint:
    """Representation of a Sensor."""

    def __init__(self, hass, ip_address):
        """Initialize the sensor."""
        self.hass = hass
        self.ip_address = ip_address
        self.data = {}
        self.ready = asyncio.Event()
        self.sensors = []

    async def async_refresh(self, now=None):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        try:
            json = await async_solax_real_time_request(self.hass,
                                                       REAL_TIME_DATA_SCHEMA,
                                                       self.ip_address,
                                                       3)
            self.data = parse_solax_battery_response(json)
            self.ready.set()
        except SolaxRequestError:
            if now is not None:
                self.ready.clear()
            else:
                raise PlatformNotReady
        for s in self.sensors:
            if s._key in self.data:
                s._value = self.data[s._key]
            s.async_schedule_update_ha_state()


class Inverter(Entity):
    def __init__(self, key):
        self._key = key
        self._value = None

    @property
    def state(self):
        return self._value

    @property
    def name(self):
        return self._key

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return INVERTER_SENSORS[self._key][1]

    @property
    def should_poll(self):
        """No polling needed."""
        return False
