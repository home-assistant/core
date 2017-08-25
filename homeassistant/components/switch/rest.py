"""
Support for RESTful switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.rest/
"""
import asyncio
import logging

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_NAME, CONF_RESOURCE, CONF_TIMEOUT, CONF_METHOD)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template import Template

_LOGGER = logging.getLogger(__name__)

CONF_BODY_OFF = 'body_off'
CONF_BODY_ON = 'body_on'
CONF_IS_ON_TEMPLATE = 'is_on_template'

DEFAULT_METHOD = 'post'
DEFAULT_BODY_OFF = Template('OFF')
DEFAULT_BODY_ON = Template('ON')
DEFAULT_NAME = 'REST Switch'
DEFAULT_TIMEOUT = 10

SUPPORT_REST_METHODS = ['post', 'put']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCE): cv.url,
    vol.Optional(CONF_BODY_OFF, default=DEFAULT_BODY_OFF): cv.template,
    vol.Optional(CONF_BODY_ON, default=DEFAULT_BODY_ON): cv.template,
    vol.Optional(CONF_IS_ON_TEMPLATE): cv.template,
    vol.Optional(CONF_METHOD, default=DEFAULT_METHOD):
        vol.All(vol.Lower, vol.In(SUPPORT_REST_METHODS)),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
})


# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the RESTful switch."""
    body_off = config.get(CONF_BODY_OFF)
    body_on = config.get(CONF_BODY_ON)
    is_on_template = config.get(CONF_IS_ON_TEMPLATE)
    method = config.get(CONF_METHOD)
    name = config.get(CONF_NAME)
    resource = config.get(CONF_RESOURCE)
    websession = async_get_clientsession(hass)

    if is_on_template is not None:
        is_on_template.hass = hass
    if body_on is not None:
        body_on.hass = hass
    if body_off is not None:
        body_off.hass = hass
    timeout = config.get(CONF_TIMEOUT)

    try:
        with async_timeout.timeout(timeout, loop=hass.loop):
            req = yield from websession.get(resource)

        if req.status >= 400:
            _LOGGER.error("Got non-ok response from resource: %s", req.status)
            return False

    except (TypeError, ValueError):
        _LOGGER.error("Missing resource or schema in configuration. "
                      "Add http:// or https:// to your URL")
        return False
    except (asyncio.TimeoutError, aiohttp.ClientError):
        _LOGGER.error("No route to resource/endpoint: %s", resource)
        return False

    async_add_devices(
        [RestSwitch(hass, name, resource, method, body_on, body_off,
                    is_on_template, timeout)])


class RestSwitch(SwitchDevice):
    """Representation of a switch that can be toggled using REST."""

    def __init__(self, hass, name, resource, method, body_on, body_off,
                 is_on_template, timeout):
        """Initialize the REST switch."""
        self._state = None
        self.hass = hass
        self._name = name
        self._resource = resource
        self._method = method
        self._body_on = body_on
        self._body_off = body_off
        self._is_on_template = is_on_template
        self._timeout = timeout

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the device on."""
        body_on_t = self._body_on.async_render()
        websession = async_get_clientsession(self.hass)

        try:
            with async_timeout.timeout(self._timeout, loop=self.hass.loop):
                request = yield from getattr(websession, self._method)(
                    self._resource, data=bytes(body_on_t, 'utf-8'))
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while turn on %s", self._resource)
            return

        if request.status == 200:
            self._state = True
        else:
            _LOGGER.error("Can't turn on %s. Is resource/endpoint offline?",
                          self._resource)

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the device off."""
        body_off_t = self._body_off.async_render()
        websession = async_get_clientsession(self.hass)

        try:
            with async_timeout.timeout(self._timeout, loop=self.hass.loop):
                request = yield from getattr(websession, self._method)(
                    self._resource, data=bytes(body_off_t, 'utf-8'))
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while turn off %s", self._resource)
            return

        if request.status == 200:
            self._state = False
        else:
            _LOGGER.error("Can't turn off %s. Is resource/endpoint offline?",
                          self._resource)

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data from REST API and update the state."""
        websession = async_get_clientsession(self.hass)

        try:
            with async_timeout.timeout(self._timeout, loop=self.hass.loop):
                request = yield from websession.get(self._resource)
                text = yield from request.text()
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.exception("Error while fetch data.")
            return

        if self._is_on_template is not None:
            text = self._is_on_template.async_render_with_possible_json_value(
                text, 'None')
            text = text.lower()
            if text == 'true':
                self._state = True
            elif text == 'false':
                self._state = False
            else:
                self._state = None
        else:
            if text == self._body_on.template:
                self._state = True
            elif text == self._body_off.template:
                self._state = False
            else:
                self._state = None
