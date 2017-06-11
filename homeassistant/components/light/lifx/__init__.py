"""
Support for the LIFX platform that implements lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.lifx/
"""
import logging
import asyncio
import sys
import math
from os import path
from functools import partial
from datetime import timedelta
import async_timeout

import voluptuous as vol

from homeassistant.components.light import (
    Light, DOMAIN, PLATFORM_SCHEMA, LIGHT_TURN_ON_SCHEMA,
    ATTR_BRIGHTNESS, ATTR_RGB_COLOR,
    ATTR_XY_COLOR, ATTR_COLOR_TEMP, ATTR_TRANSITION, ATTR_EFFECT,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_RGB_COLOR,
    SUPPORT_XY_COLOR, SUPPORT_TRANSITION, SUPPORT_EFFECT,
    preprocess_turn_on_alternatives)
from homeassistant.config import load_yaml_config_file
from homeassistant import util
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.service import extract_entity_ids
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

from . import effects as lifx_effects

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['aiolifx==0.4.8']

UDP_BROADCAST_PORT = 56700

# Delay (in ms) expected for changes to take effect in the physical bulb
BULB_LATENCY = 500

CONF_SERVER = 'server'

SERVICE_LIFX_SET_STATE = 'lifx_set_state'

ATTR_HSBK = 'hsbk'
ATTR_INFRARED = 'infrared'
ATTR_POWER = 'power'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SERVER, default='0.0.0.0'): cv.string,
})

LIFX_SET_STATE_SCHEMA = LIGHT_TURN_ON_SCHEMA.extend({
    ATTR_INFRARED: vol.All(vol.Coerce(int), vol.Clamp(min=0, max=255)),
    ATTR_POWER: cv.boolean,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the LIFX platform."""
    import aiolifx

    if sys.platform == 'win32':
        _LOGGER.warning("The lifx platform is known to not work on Windows. "
                        "Consider using the lifx_legacy platform instead")

    server_addr = config.get(CONF_SERVER)

    lifx_manager = LIFXManager(hass, async_add_devices)

    coro = hass.loop.create_datagram_endpoint(
        partial(aiolifx.LifxDiscovery, hass.loop, lifx_manager),
        local_addr=(server_addr, UDP_BROADCAST_PORT))

    hass.async_add_job(coro)

    lifx_effects.setup(hass, lifx_manager)

    return True


class LIFXManager(object):
    """Representation of all known LIFX entities."""

    def __init__(self, hass, async_add_devices):
        """Initialize the light."""
        self.entities = {}
        self.hass = hass
        self.async_add_devices = async_add_devices

        @asyncio.coroutine
        def async_service_handle(service):
            """Apply a service."""
            tasks = []
            for light in self.service_to_entities(service):
                if service.service == SERVICE_LIFX_SET_STATE:
                    task = light.async_set_state(**service.data)
                tasks.append(hass.async_add_job(task))
            if tasks:
                yield from asyncio.wait(tasks, loop=hass.loop)

        descriptions = self.get_descriptions()

        hass.services.async_register(
            DOMAIN, SERVICE_LIFX_SET_STATE, async_service_handle,
            descriptions.get(SERVICE_LIFX_SET_STATE),
            schema=LIFX_SET_STATE_SCHEMA)

    @staticmethod
    def get_descriptions():
        """Load and return descriptions for our own service calls."""
        return load_yaml_config_file(
            path.join(path.dirname(__file__), 'services.yaml'))

    def service_to_entities(self, service):
        """Return the known devices that a service call mentions."""
        entity_ids = extract_entity_ids(self.hass, service)
        if entity_ids:
            entities = [entity for entity in self.entities.values()
                        if entity.entity_id in entity_ids]
        else:
            entities = list(self.entities.values())

        return entities

    @callback
    def register(self, device):
        """Handle for newly detected bulb."""
        if device.mac_addr in self.entities:
            entity = self.entities[device.mac_addr]
            entity.device = device
            entity.registered = True
            _LOGGER.debug("%s register AGAIN", entity.who)
            self.hass.async_add_job(entity.async_update_ha_state())
        else:
            _LOGGER.debug("%s register NEW", device.ip_addr)
            device.get_version(self.got_version)

    @callback
    def got_version(self, device, msg):
        """Request current color setting once we have the product version."""
        device.get_color(self.ready)

    @callback
    def ready(self, device, msg):
        """Handle the device once all data is retrieved."""
        entity = LIFXLight(device)
        _LOGGER.debug("%s register READY", entity.who)
        self.entities[device.mac_addr] = entity
        self.async_add_devices([entity])

    @callback
    def unregister(self, device):
        """Handle disappearing bulbs."""
        if device.mac_addr in self.entities:
            entity = self.entities[device.mac_addr]
            _LOGGER.debug("%s unregister", entity.who)
            entity.registered = False
            self.hass.async_add_job(entity.async_update_ha_state())


class AwaitAioLIFX:
    """Wait for an aiolifx callback and return the message."""

    def __init__(self, light):
        """Initialize the wrapper."""
        self.light = light
        self.device = None
        self.message = None
        self.event = asyncio.Event()

    @callback
    def callback(self, device, message):
        """Handle responses."""
        self.device = device
        self.message = message
        self.event.set()

    @asyncio.coroutine
    def wait(self, method):
        """Call an aiolifx method and wait for its response or a timeout."""
        self.event.clear()
        method(self.callback)

        while self.light.available and not self.event.is_set():
            try:
                with async_timeout.timeout(1.0, loop=self.light.hass.loop):
                    yield from self.event.wait()
            except asyncio.TimeoutError:
                pass

        return self.message


def convert_8_to_16(value):
    """Scale an 8 bit level into 16 bits."""
    return (value << 8) | value


def convert_16_to_8(value):
    """Scale a 16 bit level into 8 bits."""
    return value >> 8


class LIFXLight(Light):
    """Representation of a LIFX light."""

    def __init__(self, device):
        """Initialize the light."""
        self.device = device
        self.registered = True
        self.product = device.product
        self.blocker = None
        self.effect_data = None
        self.postponed_update = None
        self._name = device.label
        self.set_power(device.power_level)
        self.set_color(*device.color)

    @property
    def lifxwhite(self):
        """Return whether this is a white-only bulb."""
        # https://lan.developer.lifx.com/docs/lifx-products
        return self.product in [10, 11, 18]

    @property
    def available(self):
        """Return the availability of the device."""
        return self.registered

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def who(self):
        """Return a string identifying the device."""
        ip_addr = '-'
        if self.device:
            ip_addr = self.device.ip_addr[0]
        return "%s (%s)" % (ip_addr, self.name)

    @property
    def rgb_color(self):
        """Return the RGB value."""
        _LOGGER.debug(
            "rgb_color: [%d %d %d]", self._rgb[0], self._rgb[1], self._rgb[2])
        return self._rgb

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        brightness = convert_16_to_8(self._bri)
        _LOGGER.debug("brightness: %d", brightness)
        return brightness

    @property
    def color_temp(self):
        """Return the color temperature."""
        temperature = color_util.color_temperature_kelvin_to_mired(self._kel)

        _LOGGER.debug("color_temp: %d", temperature)
        return temperature

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        # The 3 LIFX "White" products supported a limited temperature range
        if self.lifxwhite:
            kelvin = 6500
        else:
            kelvin = 9000
        return math.floor(color_util.color_temperature_kelvin_to_mired(kelvin))

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        # The 3 LIFX "White" products supported a limited temperature range
        if self.lifxwhite:
            kelvin = 2700
        else:
            kelvin = 2500
        return math.ceil(color_util.color_temperature_kelvin_to_mired(kelvin))

    @property
    def is_on(self):
        """Return true if device is on."""
        _LOGGER.debug("is_on: %d", self._power)
        return self._power != 0

    @property
    def effect(self):
        """Return the currently running effect."""
        return self.effect_data.effect.name if self.effect_data else None

    @property
    def supported_features(self):
        """Flag supported features."""
        features = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP |
                    SUPPORT_TRANSITION | SUPPORT_EFFECT)

        if not self.lifxwhite:
            features |= SUPPORT_RGB_COLOR | SUPPORT_XY_COLOR

        return features

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return lifx_effects.effect_list(self)

    @asyncio.coroutine
    def update_after_transition(self, now):
        """Request new status after completion of the last transition."""
        self.postponed_update = None
        yield from self.refresh_state()
        yield from self.async_update_ha_state()

    @asyncio.coroutine
    def unblock_updates(self, now):
        """Allow async_update after the new state has settled on the bulb."""
        self.blocker = None
        yield from self.refresh_state()
        yield from self.async_update_ha_state()

    def update_later(self, when):
        """Block immediate update requests and schedule one for later."""
        if self.blocker:
            self.blocker()
        self.blocker = async_track_point_in_utc_time(
            self.hass, self.unblock_updates,
            util.dt.utcnow() + timedelta(milliseconds=BULB_LATENCY))

        if self.postponed_update:
            self.postponed_update()
            self.postponed_update = None
        if when > BULB_LATENCY:
            self.postponed_update = async_track_point_in_utc_time(
                self.hass, self.update_after_transition,
                util.dt.utcnow() + timedelta(milliseconds=when+BULB_LATENCY))

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the device on."""
        kwargs[ATTR_POWER] = True
        yield from self.async_set_state(**kwargs)

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the device off."""
        kwargs[ATTR_POWER] = False
        yield from self.async_set_state(**kwargs)

    @asyncio.coroutine
    def async_set_state(self, **kwargs):
        """Set a color on the light and turn it on/off."""
        yield from self.stop_effect()

        if ATTR_EFFECT in kwargs:
            yield from lifx_effects.default_effect(self, **kwargs)
            return

        if ATTR_INFRARED in kwargs:
            self.device.set_infrared(convert_8_to_16(kwargs[ATTR_INFRARED]))

        if ATTR_TRANSITION in kwargs:
            fade = int(kwargs[ATTR_TRANSITION] * 1000)
        else:
            fade = 0

        # These are both False if ATTR_POWER is not set
        power_on = kwargs.get(ATTR_POWER, False)
        power_off = not kwargs.get(ATTR_POWER, True)

        hsbk, changed_color = self.find_hsbk(**kwargs)
        _LOGGER.debug("turn_on: %s (%d) %d %d %d %d %d",
                      self.who, self._power, fade, *hsbk)

        if self._power == 0:
            if power_off:
                self.device.set_power(False, None, 0)
            if changed_color:
                self.device.set_color(hsbk, None, 0)
            if power_on:
                self.device.set_power(True, None, fade)
        else:
            if power_on:
                self.device.set_power(True, None, 0)
            if changed_color:
                self.device.set_color(hsbk, None, fade)
            if power_off:
                self.device.set_power(False, None, fade)

        if power_on:
            self.update_later(0)
        else:
            self.update_later(fade)

        if fade <= BULB_LATENCY:
            if power_on:
                self.set_power(1)
            if power_off:
                self.set_power(0)
            if changed_color:
                self.set_color(*hsbk)

    @asyncio.coroutine
    def async_update(self):
        """Update bulb status (if it is available)."""
        _LOGGER.debug("%s async_update", self.who)
        if self.blocker is None:
            yield from self.refresh_state()

    @asyncio.coroutine
    def stop_effect(self):
        """Stop the currently running effect (if any)."""
        if self.effect_data:
            yield from self.effect_data.effect.async_restore(self)

    @asyncio.coroutine
    def refresh_state(self):
        """Ask the device about its current state and update our copy."""
        if self.available:
            msg = yield from AwaitAioLIFX(self).wait(self.device.get_color)
            if msg is not None:
                self.set_power(self.device.power_level)
                self.set_color(*self.device.color)
                self._name = self.device.label

    def find_hsbk(self, **kwargs):
        """Find the desired color from a number of possible inputs."""
        changed_color = False

        hsbk = kwargs.pop(ATTR_HSBK, None)
        if hsbk is not None:
            return [hsbk, True]

        preprocess_turn_on_alternatives(kwargs)

        if ATTR_RGB_COLOR in kwargs:
            hue, saturation, brightness = \
                color_util.color_RGB_to_hsv(*kwargs[ATTR_RGB_COLOR])
            saturation = convert_8_to_16(saturation)
            brightness = convert_8_to_16(brightness)
            changed_color = True
        else:
            hue = self._hue
            saturation = self._sat
            brightness = self._bri

        if ATTR_XY_COLOR in kwargs:
            hue, saturation = color_util.color_xy_to_hs(*kwargs[ATTR_XY_COLOR])
            saturation = convert_8_to_16(saturation)
            changed_color = True

        # When color or temperature is set, use a default value for the other
        if ATTR_COLOR_TEMP in kwargs:
            kelvin = int(color_util.color_temperature_mired_to_kelvin(
                kwargs[ATTR_COLOR_TEMP]))
            if not changed_color:
                saturation = 0
            changed_color = True
        else:
            if changed_color:
                kelvin = 3500
            else:
                kelvin = self._kel

        if ATTR_BRIGHTNESS in kwargs:
            brightness = convert_8_to_16(kwargs[ATTR_BRIGHTNESS])
            changed_color = True
        else:
            brightness = self._bri

        return [[hue, saturation, brightness, kelvin], changed_color]

    def set_power(self, power):
        """Set power state value."""
        _LOGGER.debug("set_power: %d", power)
        self._power = (power != 0)

    def set_color(self, hue, sat, bri, kel):
        """Set color state values."""
        self._hue = hue
        self._sat = sat
        self._bri = bri
        self._kel = kel

        red, green, blue = color_util.color_hsv_to_RGB(
            hue, convert_16_to_8(sat), convert_16_to_8(bri))

        _LOGGER.debug("set_color: %d %d %d %d [%d %d %d]",
                      hue, sat, bri, kel, red, green, blue)

        self._rgb = [red, green, blue]
