"""
Support for the elan Thermostat.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/xxxx/
"""

import asyncio
import logging
import voluptuous as vol

from homeassistant.const import TEMP_CELSIUS
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.aiohttp_client import async_get_clientsession

DOMAIN = 'elan'

_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required('url'): cv.string,
    vol.Optional('offsets'): {
        cv.string: vol.Coerce(float)
    },
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the elan thermostat platform."""
    if discovery_info is None:
        return

    url = discovery_info['url']

    session = async_get_clientsession(hass)
    resp = yield from session.get(url + '/api/devices', timeout=3)
    device_list = yield from resp.json()
    _LOGGER.info("elan devices")
    _LOGGER.info(device_list)
    _LOGGER.info(str(config))

    temperature_offsets = {}

    if 'offsets' in config:
        if isinstance(config['offsets'], dict):
            temperature_offsets = config['offsets']
            _LOGGER.info(temperature_offsets)

    if 'offsets' in discovery_info:
        if isinstance(discovery_info['offsets'], dict):
            temperature_offsets = discovery_info['offsets']
            _LOGGER.info(temperature_offsets)

    for device in device_list:
        resp = yield from session.get(device_list[device]['url'], timeout=3)
        info = yield from resp.json()
        if info['device info']['type'] == 'heating':
            _LOGGER.info("Adding elan Thermostat %s",
                         device_list[device]['url'])
            async_add_devices([
                ElanThermostat(
                    session, device_list[device]['url'], info, 'temperature',
                    temperature_offsets.get(device_list[device]['url'], 0))
            ])
            async_add_devices([
                ElanThermostat(session, device_list[device]['url'], info, 'on')
            ])


class ElanThermostat(Entity):
    """The platform class required by Home Assistant."""

    def __init__(self, session, thermostat, info, var, offset=0):
        """Initialize a thermostat."""
        _LOGGER.info("elan thermostat %s initialisation",
                     info['device info']['label'])
        _LOGGER.info(info)
        self._thermostat = thermostat
        self._var = 'temperature'
        self._info = info
        self._state = None
        self._name = info['device info']['label']
        self._temperature_in = None
        self._temperature_out = None
        self._temperature_offset = offset
        self._on = None
        self._locked = None
        self._units = None
        if var is 'temperature':
            self._name = info['device info']['label'] + '-T'
            self._var = var
            self._units = TEMP_CELSIUS

        if var is 'temperature OUT':
            self._name = info['device info']['label'] + '-T OUT'
            self._var = var
            self._units = TEMP_CELSIUS

        if var is 'temperature IN':
            self._name = info['device info']['label'] + '-T IN'
            self._var = var
            self._units = TEMP_CELSIUS

        if var is 'on':
            self._name = info['device info']['label'] + '-ON'
            self._var = var

        self._temperature_offset = offset

        self._session = session

        self._available = True

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Start thread when added to hass."""

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def should_poll(self):
        """WS notification not implemented yet - polling is needed."""
        return True

    @property
    def name(self):
        """Return the display name of this thermostat."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._units

    @asyncio.coroutine
    def update(self):
        """Fetch new state data for this thermostat.

        This is the only method that should fetch new data for Home Assistant.
        """
        stateurl = self._thermostat + '/state'
        _LOGGER.debug('Getting elan thermostat %s update', stateurl)
        resp = yield from self._session.get(stateurl, timeout=3)
        state = yield from resp.json()
        _LOGGER.debug(state)
        if 'temperature IN' in state:
            self._temperature_in = state['temperature IN']

        if 'temperature OUT' in state:
            self._temperature_out = state['temperature OUT']

        if 'on' in state:
            self._on = state['on']
        if 'locked' in state:
            self._locked = state['locked']

        if self._var is 'temperature':
            if self._temperature_in and (self._temperature_in > -99):
                self._state = self._temperature_in + self._temperature_offset
            if self._temperature_out and (self._temperature_out > -99):
                self._state = self._temperature_out + self._temperature_offset

        if self._var is 'temperature OUT':
            if self._temperature_out and (self._temperature_out > -99):
                self._state = self._temperature_out + self._temperature_offset

        if self._var is 'temperature IN':
            if self._temperature_in and (self._temperature_in > -99):
                self._state = self._temperature_in + self._temperature_offset

        if self._var is 'on':
            self._state = self._on

        _LOGGER.debug(self._state)
