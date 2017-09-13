import logging
import asyncio

import aiohttp
import async_timeout

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

from homeassistant.helpers.entity import Entity
from homeassistant.components.switch import (PLATFORM_SCHEMA)
from homeassistant.const import (CONF_HOST, CONF_PIN, CONF_TYPE, CONF_TIMEOUT)
from homeassistant.helpers.aiohttp_client import (async_get_clientsession)

_LOGGER = logging.getLogger(__name__)

CONF_ALLOW_UNREACHABLE = 'allow_unreachable'

DEFAULT_TIMEOUT = 5

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PIN): vol.All(vol.Coerce(int), vol.Range(min=1000, max=9999)),
    vol.Optional(CONF_ALLOW_UNREACHABLE, default=True): cv.boolean,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
})

ERROR_STATE = [
    'blade-blocked',
    'repositioning-error',
    'wire-bounced',
    'blade-blocked',
    'outside-wire',
    'mower-lifted',
    'alarm-6',
    'upside-down',
    'alarm-8',
    'collision-sensor-blocked',
    'mower-tilted',
    'charge-error',
    'battery-error'
]

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    async_add_entities([WorxLandroidSensor('battery', hass, config)])
    async_add_entities([WorxLandroidSensor('error', hass, config)])
    async_add_entities([WorxLandroidSensor('state', hass, config)])

class WorxLandroidSensor(Entity):

    def __init__(self, type, hass, config):
        self._state = None
        self.hass = hass
        self.type = type
        self.host = config.get(CONF_HOST)
        self.pin = config.get(CONF_PIN)
        self.timeout = config.get(CONF_TIMEOUT)
        self.allow_unreachable = config.get(CONF_ALLOW_UNREACHABLE)
        self.url = 'http://{}/jsondata.cgi'.format(self.host)

    @property
    def name(self):
        return 'worx-landroid-{}'.format(self.type)

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        if self.type == 'battery':
            return '%'
        else:
            return None

    @asyncio.coroutine
    def async_update(self):
        _LOGGER.debug("Updating mower %s from %s", self.type, self.url)

        connection_error = False

        try:
            httpsession = async_get_clientsession(self.hass)
            with async_timeout.timeout(self.timeout, loop=self.hass.loop):
                mower_response = yield from httpsession.get(self.url, auth=aiohttp.helpers.BasicAuth('admin', self.pin))
        except (asyncio.TimeoutError, aiohttp.ClientError):
            if self.allow_unreachable is False:
                _LOGGER.error("Error connecting to mower at %s", self.url)

            connection_error = True

        # connection error
        if connection_error is True and self.allow_unreachable is False:
            if self.type == 'error':
                self._state = 'yes'
            elif self.type == 'state':
                self._state = 'connection-error'

        # connection success
        elif connection_error is False:
            # set the expected content type to be text/html since the mover incorrectly returns it...
            data = yield from mower_response.json(content_type='text/html')

            # type battery
            if self.type == 'battery':
                self._state = data['perc_batt']

            # type error
            elif self.type == 'error':
                self._state = 'no' if self.get_error(data) is None else 'yes'

            # type state
            elif self.type == 'state':
                self._state = self.get_state(data)

        else:
            if type == 'error':
                self._state = 'no'

    def get_error(self, obj):
        for i, err in enumerate(obj['allarmi']):
            if i != 2: # ignore wire bounce errors
                if err == 1:
                    return ERROR_STATE[i]

        return None

    def get_state(self, obj):
        state = self.get_error(obj)

        if state is None:
            state_obj = obj['settaggi']

            if state_obj[14] == 1:
                return 'manual-stop'
            elif state_obj[5] == 1 and state_obj[13] == 0:
                return 'charging'
            elif state_obj[5] == 1 and state_obj[13] == 1:
                return 'charging-complete'
            elif state_obj[15] == 1:
                return 'going-home'
            else:
                return 'mowing'

        return state
