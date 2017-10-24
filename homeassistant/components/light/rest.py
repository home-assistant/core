"""
Support for RESTful lights.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.rest/

Code adapted from the RESTful switch implementation.
"""
import asyncio
import logging

import aiohttp
import async_timeout
import voluptuous as vol

import ast
import json

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, ATTR_COLOR_TEMP, SUPPORT_COLOR_TEMP,
    ATTR_EFFECT, SUPPORT_EFFECT, ATTR_RGB_COLOR, SUPPORT_RGB_COLOR,
    ATTR_TRANSITION, SUPPORT_TRANSITION, Light, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_NAME, CONF_RESOURCE, CONF_TIMEOUT, CONF_METHOD, CONF_USERNAME,
    CONF_PASSWORD)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template import Template

_LOGGER = logging.getLogger(__name__)

CONF_BODY_OFF = 'body_off'
CONF_BODY_ON = 'body_on'
CONF_BODY_BRIGHTNESS = 'body_brightness'
CONF_BODY_COLOR_TEMP = 'body_color_temp'
CONF_BODY_EFFECT = 'body_effect'
CONF_BODY_RGB_COLOR = 'body_rgb_color'
CONF_BODY_TRANSITION = 'body_transition'
CONF_IS_ON_TEMPLATE = 'is_on_template'
CONF_BRIGHTNESS_TEMPLATE = 'brightness_template'
CONF_COLOR_TEMP_TEMPLATE = 'color_temp_template'
CONF_EFFECT_TEMPLATE = 'effect_template'
CONF_RGB_COLOR_TEMPLATE = 'rgb_color_template'
CONF_NAME_TEMPLATE = 'name_template'
CONF_SUPPORTED_FEATURES_TEMPLATE = 'supported_features_template'
CONF_SUPPORTED_FEATURES = 'supported_features'
CONF_EFFECT_LIST_TEMPLATE = 'effect_list_template'

DEFAULT_METHOD = 'post'
DEFAULT_BODY_OFF = Template('{"is_on": false}')
DEFAULT_BODY_ON = Template('{"is_on": true}')
DEFAULT_BODY_BRIGHTNESS = Template('{"brightness": %d}')
DEFAULT_BODY_COLOR_TEMP = Template('{"color_temp": %d}')
DEFAULT_BODY_EFFECT = Template('{"effect": "%s"}')
DEFAULT_BODY_RGB_COLOR = Template('{"rgb_color": [%d, %d, %d]}')
DEFAULT_BODY_TRANSITION = Template('{"transition": %d}')
DEFAULT_IS_ON_TEMPLATE = Template('{{value_json.is_on}}')
DEFAULT_BRIGHTNESS_TEMPLATE = Template('{{value_json.brightness}}')
DEFAULT_COLOR_TEMP_TEMPLATE = Template('{{value_json.color_temp}}')
DEFAULT_EFFECT_TEMPLATE = Template('{{value_json.effect}}')
DEFAULT_RGB_COLOR_TEMPLATE = Template('{{value_json.rgb_color}}')
DEFAULT_NAME_TEMPLATE = Template('{{value_json.name}}')
DEFAULT_SUPPORTED_FEATURES_TEMPLATE = Template(
    '{{value_json.supported_features}}')
DEFAULT_EFFECT_LIST_TEMPLATE = Template('{{value_json.effect_list}}')
DEFAULT_SUPPORTED_FEATURES = ['brightness']
DEFAULT_NAME = 'REST Light'
DEFAULT_TIMEOUT = 10

SUPPORT_REST_METHODS = ['post', 'put']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCE): cv.url,
    vol.Optional(CONF_BODY_OFF, default=DEFAULT_BODY_OFF): cv.template,
    vol.Optional(CONF_BODY_ON, default=DEFAULT_BODY_ON): cv.template,
    vol.Optional(CONF_BODY_BRIGHTNESS,
                 default=DEFAULT_BODY_BRIGHTNESS): cv.template,
    vol.Optional(CONF_BODY_COLOR_TEMP,
                 default=DEFAULT_BODY_COLOR_TEMP): cv.template,
    vol.Optional(CONF_BODY_EFFECT, default=DEFAULT_BODY_EFFECT): cv.template,
    vol.Optional(CONF_BODY_RGB_COLOR,
                 default=DEFAULT_BODY_RGB_COLOR): cv.template,
    vol.Optional(CONF_BODY_TRANSITION,
                 default=DEFAULT_BODY_TRANSITION): cv.template,
    vol.Optional(CONF_IS_ON_TEMPLATE,
                 default=DEFAULT_IS_ON_TEMPLATE): cv.template,
    vol.Optional(CONF_BRIGHTNESS_TEMPLATE,
                 default=DEFAULT_BRIGHTNESS_TEMPLATE): cv.template,
    vol.Optional(CONF_COLOR_TEMP_TEMPLATE,
                 default=DEFAULT_COLOR_TEMP_TEMPLATE): cv.template,
    vol.Optional(CONF_EFFECT_TEMPLATE,
                 default=DEFAULT_EFFECT_TEMPLATE): cv.template,
    vol.Optional(CONF_RGB_COLOR_TEMPLATE,
                 default=DEFAULT_RGB_COLOR_TEMPLATE): cv.template,
    vol.Optional(CONF_NAME_TEMPLATE,
                 default=DEFAULT_NAME_TEMPLATE): cv.template,
    vol.Optional(CONF_SUPPORTED_FEATURES_TEMPLATE,
                 default=DEFAULT_SUPPORTED_FEATURES_TEMPLATE): cv.template,
    vol.Optional(CONF_EFFECT_LIST_TEMPLATE,
                 default=DEFAULT_EFFECT_LIST_TEMPLATE): cv.template,
    vol.Optional(CONF_METHOD, default=DEFAULT_METHOD):
        vol.All(vol.Lower, vol.In(SUPPORT_REST_METHODS)),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SUPPORTED_FEATURES,
                 default=DEFAULT_SUPPORTED_FEATURES): vol.Coerce(tuple),
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    vol.Inclusive(CONF_USERNAME, 'authentication'): cv.string,
    vol.Inclusive(CONF_PASSWORD, 'authentication'): cv.string,
})


# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the RESTful switch."""
    body_off = config.get(CONF_BODY_OFF)
    body_on = config.get(CONF_BODY_ON)
    body_brightness = config.get(CONF_BODY_BRIGHTNESS)
    body_color_temp = config.get(CONF_BODY_COLOR_TEMP)
    body_effect = config.get(CONF_BODY_EFFECT)
    body_rgb_color = config.get(CONF_BODY_RGB_COLOR)
    body_transition = config.get(CONF_BODY_TRANSITION)
    is_on_template = config.get(CONF_IS_ON_TEMPLATE)
    brightness_template = config.get(CONF_BRIGHTNESS_TEMPLATE)
    color_temp_template = config.get(CONF_COLOR_TEMP_TEMPLATE)
    effect_template = config.get(CONF_EFFECT_TEMPLATE)
    rgb_color_template = config.get(CONF_RGB_COLOR_TEMPLATE)
    name_template = config.get(CONF_NAME_TEMPLATE)
    supported_features_template = config.get(CONF_SUPPORTED_FEATURES_TEMPLATE)
    effect_list_template = config.get(CONF_EFFECT_LIST_TEMPLATE)
    method = config.get(CONF_METHOD)
    supported_features = config.get(CONF_SUPPORTED_FEATURES)
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    resource = config.get(CONF_RESOURCE)

    auth = None
    if username:
        auth = aiohttp.BasicAuth(username, password=password)

    if is_on_template is not None:
        is_on_template.hass = hass
    if brightness_template is not None:
        brightness_template.hass = hass
    if color_temp_template is not None:
        color_temp_template.hass = hass
    if effect_template is not None:
        effect_template.hass = hass
    if rgb_color_template is not None:
        rgb_color_template.hass = hass
    if name_template is not None:
        name_template.hass = hass
    if supported_features_template is not None:
        supported_features_template.hass = hass
    if effect_list_template is not None:
        effect_list_template.hass = hass
    if body_on is not None:
        body_on.hass = hass
    if body_off is not None:
        body_off.hass = hass
    if body_brightness is not None:
        body_brightness.hass = hass
    if body_color_temp is not None:
        body_color_temp.hass = hass
    if body_effect is not None:
        body_effect.hass = hass
    if body_rgb_color is not None:
        body_rgb_color.hass = hass
    if body_transition is not None:
        body_transition.hass = hass
    timeout = config.get(CONF_TIMEOUT)

    try:
        light = RestLight(name, resource, method, auth, body_on, body_off,
                          body_brightness, body_color_temp, body_effect,
                          body_rgb_color, body_transition, is_on_template,
                          brightness_template, color_temp_template,
                          effect_template, rgb_color_template, name_template,
                          supported_features_template, effect_list_template,
                          supported_features, timeout)

        req = yield from light.get_device_state(hass)
        if req.status >= 400:
            _LOGGER.error("Got non-ok response from resource: %s", req.status)
        else:
            async_add_devices([light])
    except (TypeError, ValueError):
        _LOGGER.error("Missing resource or schema in configuration. "
                      "Add http:// or https:// to your URL")
    except (asyncio.TimeoutError, aiohttp.ClientError):
        _LOGGER.error("No route to resource/endpoint: %s", resource)


class RestLight(Light):
    """Representation of a light that can be toggled using REST."""

    def __init__(self, name, resource, method, auth, body_on, body_off,
                 body_brightness, body_color_temp, body_effect, body_rgb_color,
                 body_transition, is_on_template, brightness_template,
                 color_temp_template, effect_template, rgb_color_template,
                 name_template, supported_features_template,
                 effect_list_template, supported_features, timeout):
        """Initialize the REST light."""
        self._state = None
        self._brightness = None
        self._color_temp = None
        self._effect = None
        self._effect_list = []
        self._supported_features = supported_features
        self._rgb_color = [None, None, None]
        self._transition = None
        self._name = name
        self._resource = resource
        self._method = method
        self._auth = auth
        self._body_on = body_on
        self._body_off = body_off
        self._body_brightness = body_brightness
        self._body_color_temp = body_color_temp
        self._body_effect = body_effect
        self._body_rgb_color = body_rgb_color
        self._body_transition = body_transition
        self._is_on_template = is_on_template
        self._brightness_template = brightness_template
        self._color_temp_template = color_temp_template
        self._effect_template = effect_template
        self._rgb_color_template = rgb_color_template
        self._name_template = name_template
        self._supported_features_template = supported_features_template
        self._effect_list_template = effect_list_template
        self._timeout = timeout

    @property
    def name(self):
        """Return the name of the light."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def brightness(self):
        """Read back the brightness of the light."""
        if "brightness" in self._supported_features:
            return self._brightness
        else:
            return None

    @property
    def color_temp(self):
        """Read back the color_temp of the light."""
        if "color_temp" in self._supported_features:
            return self._color_temp
        else:
            return None

    @property
    def effect(self):
        """Read back the effect of the light."""
        if "effect" in self._supported_features:
            return self._effect
        else:
            return None

    @property
    def rgb_color(self):
        """Read back the rgb_color of the light."""
        if "rgb_color" in self._supported_features:
            return self._rgb_color
        else:
            return None

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = 0
        if "brightness" in self._supported_features:
            supported_features = (supported_features | SUPPORT_BRIGHTNESS)
        if "color_temp" in self._supported_features:
            supported_features = (supported_features | SUPPORT_COLOR_TEMP)
        if "effect" in self._supported_features:
            supported_features = (supported_features | SUPPORT_EFFECT)
        if "rgb_color" in self._supported_features:
            supported_features = (supported_features | SUPPORT_RGB_COLOR)
        if "transition" in self._supported_features:
            supported_features = (supported_features | SUPPORT_TRANSITION)

        return supported_features

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        if "effect" in self._supported_features:
            return self._effect_list
        else:
            return None

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the device on."""
        body_on_t = self._body_on.async_render()
        body_on_dict = json.loads(body_on_t)

        if ATTR_BRIGHTNESS in kwargs:
            body_brightness_t = self._body_brightness.async_render() % \
                kwargs[ATTR_BRIGHTNESS]
            brightness_dict = json.loads(body_brightness_t)
            body_on_dict.update(brightness_dict)
        if ATTR_COLOR_TEMP in kwargs:
            body_color_temp_t = self._body_color_temp.async_render() % \
                kwargs[ATTR_COLOR_TEMP]
            color_temp_dict = json.loads(body_color_temp_t)
            body_on_dict.update(color_temp_dict)
        if ATTR_EFFECT in kwargs:
            body_effect_t = self._body_effect.async_render() % \
                kwargs[ATTR_EFFECT]
            effect_dict = json.loads(body_effect_t)
            body_on_dict.update(effect_dict)
        if ATTR_RGB_COLOR in kwargs:
            body_rgb_color_t = self._body_rgb_color.async_render() % \
                tuple(kwargs[ATTR_RGB_COLOR])
            rgb_color_dict = json.loads(body_rgb_color_t)
            body_on_dict.update(rgb_color_dict)
        if ATTR_TRANSITION in kwargs:
            body_transition_t = self._body_transition.async_render() % \
                kwargs[ATTR_TRANSITION]
            transition_dict = json.loads(body_transition_t)
            body_on_dict.update(transition_dict)

        body_on_t = json.dumps(body_on_dict)

        try:
            req = yield from self.set_device_state(body_on_t)

            if req.status == 200:
                self._state = True
            else:
                _LOGGER.error(
                    "Can't turn on %s. Is resource/endpoint offline?",
                    self._resource)
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while turn on %s", self._resource)

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the device off."""
        body_off_t = self._body_off.async_render()

        try:
            req = yield from self.set_device_state(body_off_t)
            if req.status == 200:
                self._state = False
            else:
                _LOGGER.error(
                    "Can't turn off %s. Is resource/endpoint offline?",
                    self._resource)
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while turn off %s", self._resource)

    @asyncio.coroutine
    def set_device_state(self, body):
        """Send a state update to the device."""
        websession = async_get_clientsession(self.hass)

        with async_timeout.timeout(self._timeout, loop=self.hass.loop):
            req = yield from getattr(websession, self._method)(
                self._resource, auth=self._auth, data=bytes(body, 'utf-8'))
            return req

    @asyncio.coroutine
    def async_update(self):
        """Get the current state, catching errors."""
        try:
            yield from self.get_device_state(self.hass)
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.exception("Error while fetch data.")

    @asyncio.coroutine
    def get_device_state(self, hass):
        """Get the latest data from REST API and update the state."""
        websession = async_get_clientsession(hass)

        with async_timeout.timeout(self._timeout, loop=hass.loop):
            req = yield from websession.get(self._resource, auth=self._auth)
            text = yield from req.text()

        result = self._is_on_template.async_render_with_possible_json_value(
                text, 'None')
        result = result.lower()
        if result == 'true':
            self._state = True
        elif result == 'false':
            self._state = False
        else:
            self._state = None

        result = self._supported_features_template.\
            async_render_with_possible_json_value(text, '')
        if result != '':
            self._supported_features = ast.literal_eval(result)

        if "brightness" in self._supported_features:
            result = self._brightness_template.\
                async_render_with_possible_json_value(text, 0)
            self._brightness = int(result)

        if "color_temp" in self._supported_features:
            result = self._color_temp_template.\
                async_render_with_possible_json_value(text, 0)
            self._color_temp = int(result)

        if "effect" in self._supported_features:
            result = self._effect_template.\
                async_render_with_possible_json_value(text, '')
            self._effect = result
            result = self._effect_list_template.\
                async_render_with_possible_json_value(text, '[]')
            self._effect_list = ast.literal_eval(result)

        if "rgb_color" in self._supported_features:
            result = self._rgb_color_template.\
                async_render_with_possible_json_value(text, '[]')
            self._rgb_color = ast.literal_eval(result)

        result = self._name_template.\
            async_render_with_possible_json_value(text, self._name)
        self._name = result

        return req
