"""
Support for the elan Lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/xxxx/
"""

import asyncio
import logging
import voluptuous as vol

from homeassistant.components.light import (ATTR_BRIGHTNESS,
                                            SUPPORT_BRIGHTNESS, Light)
from homeassistant.components.light import PLATFORM_SCHEMA
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required('url'): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the elan Light platform."""
    if discovery_info is None:
        return

    url = discovery_info['url']

    session = async_get_clientsession(hass)
    resp = yield from session.get(url + '/api/devices', timeout=3)
    device_list = yield from resp.json()
    _LOGGER.info("elan devices")
    _LOGGER.info(device_list)

    for device in device_list:
        resp = yield from session.get(device_list[device]['url'], timeout=3)
        info = yield from resp.json()
        if info['device info']['type'] == 'light':
            _LOGGER.info("Adding elan Light %s", device_list[device]['url'])
            async_add_devices(
                [ElanLight(session, device_list[device]['url'], info)])


class ElanLight(Light):
    """The platform class required by Home Assistant."""

    def __init__(self, session, light, info):
        """Initialize a Light."""
        _LOGGER.info("elan light %s initialisation",
                     info['device info']['label'])
        self._light = light
        self._info = info
        self._name = info['device info']['label']
        self._state = None
        self._brightness = None

        self._last_brightness = 100
        self._dimmer = False
        self._available = True
        self._features = None
        self._rgb_color = None

        self._features = 0

        if info['primary actions'][0] == 'brightness':
            self._features = SUPPORT_BRIGHTNESS
            self._dimmer = True

        self._session = session

    @property
    def device_state_attributes(self):
        """Return the devices' state attributes."""
        attrs = {}
        return attrs

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
    def supported_features(self):
        """Flag supported features."""
        return self._features

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def rgb_color(self):
        """RGB color of the light."""
        return self._rgb_color

    @asyncio.coroutine
    def update(self):
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assistant.
        """
        stateurl = self._light + '/state'
        _LOGGER.debug('Getting elan Light %s update', stateurl)
        resp = yield from self._session.get(stateurl, timeout=3)
        state = yield from resp.json()
        _LOGGER.debug(state)
        tmp = False
        if 'on' in state:
            tmp = state['on']
        if 'brightness' in state:
            self._brightness = state['brightness']
            if state['brightness'] > 0:
                tmp = True
        self._state = tmp

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        _LOGGER.debug('Turning off elan light %s', self._name)
        if self._dimmer:
            resp = yield from self._session.put(
                self._light, json={'brightness': 0})
        else:
            resp = yield from self._session.put(
                self._light, json={'on': False})
        info = yield from resp.text()
        _LOGGER.debug(info)

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        _LOGGER.debug('Turning on elan light %s', self._name)
        if ATTR_BRIGHTNESS in kwargs:
            if kwargs[ATTR_BRIGHTNESS] > 0:
                self._last_brightness = kwargs[ATTR_BRIGHTNESS]

        if self._dimmer:
            if self._last_brightness is 0:
                self._last_brightness = 100
            resp = yield from self._session.put(
                self._light, json={'brightness': self._last_brightness})
        else:
            resp = yield from self._session.put(self._light, json={'on': True})

        info = yield from resp.text()
        _LOGGER.debug(info)
