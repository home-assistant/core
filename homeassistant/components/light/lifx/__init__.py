"""
Support for the LIFX platform that implements lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.lifx/
"""
import colorsys
import logging
import asyncio
import sys
import math
from functools import partial
from datetime import timedelta
import async_timeout

import voluptuous as vol

from homeassistant.components.light import (
    Light, PLATFORM_SCHEMA, ATTR_BRIGHTNESS, ATTR_COLOR_NAME, ATTR_RGB_COLOR,
    ATTR_XY_COLOR, ATTR_COLOR_TEMP, ATTR_TRANSITION, ATTR_EFFECT,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_RGB_COLOR,
    SUPPORT_XY_COLOR, SUPPORT_TRANSITION, SUPPORT_EFFECT)
from homeassistant.util.color import (
    color_temperature_mired_to_kelvin, color_temperature_kelvin_to_mired)
from homeassistant import util
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_utc_time
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

from . import effects as lifx_effects

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['aiolifx==0.4.6']

UDP_BROADCAST_PORT = 56700

# Delay (in ms) expected for changes to take effect in the physical bulb
BULB_LATENCY = 500

CONF_SERVER = 'server'

ATTR_HSBK = 'hsbk'

BYTE_MAX = 255
SHORT_MAX = 65535

SUPPORT_LIFX = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_RGB_COLOR |
                SUPPORT_XY_COLOR | SUPPORT_TRANSITION | SUPPORT_EFFECT)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SERVER, default='0.0.0.0'): cv.string,
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


def convert_rgb_to_hsv(rgb):
    """Convert Home Assistant RGB values to HSV values."""
    red, green, blue = [_ / BYTE_MAX for _ in rgb]

    hue, saturation, brightness = colorsys.rgb_to_hsv(red, green, blue)

    return [int(hue * SHORT_MAX),
            int(saturation * SHORT_MAX),
            int(brightness * SHORT_MAX)]


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
        brightness = int(self._bri / (BYTE_MAX + 1))
        _LOGGER.debug("brightness: %d", brightness)
        return brightness

    @property
    def color_temp(self):
        """Return the color temperature."""
        temperature = color_temperature_kelvin_to_mired(self._kel)

        _LOGGER.debug("color_temp: %d", temperature)
        return temperature

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        # The 3 LIFX "White" products supported a limited temperature range
        # https://lan.developer.lifx.com/docs/lifx-products
        if self.product in [10, 11, 18]:
            kelvin = 6500
        else:
            kelvin = 9000
        return math.floor(color_temperature_kelvin_to_mired(kelvin))

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        # The 3 LIFX "White" products supported a limited temperature range
        # https://lan.developer.lifx.com/docs/lifx-products
        if self.product in [10, 11, 18]:
            kelvin = 2700
        else:
            kelvin = 2500
        return math.ceil(color_temperature_kelvin_to_mired(kelvin))

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
        return SUPPORT_LIFX

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return lifx_effects.effect_list()

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
        yield from self.stop_effect()

        if ATTR_EFFECT in kwargs:
            yield from lifx_effects.default_effect(self, **kwargs)
            return

        if ATTR_TRANSITION in kwargs:
            fade = int(kwargs[ATTR_TRANSITION] * 1000)
        else:
            fade = 0

        hsbk, changed_color = self.find_hsbk(**kwargs)
        _LOGGER.debug("turn_on: %s (%d) %d %d %d %d %d",
                      self.who, self._power, fade, *hsbk)

        if self._power == 0:
            if changed_color:
                self.device.set_color(hsbk, None, 0)
            self.device.set_power(True, None, fade)
        else:
            self.device.set_power(True, None, 0)     # racing for power status
            if changed_color:
                self.device.set_color(hsbk, None, fade)

        self.update_later(0)
        if fade < BULB_LATENCY:
            self.set_power(1)
            self.set_color(*hsbk)

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the device off."""
        yield from self.stop_effect()

        if ATTR_TRANSITION in kwargs:
            fade = int(kwargs[ATTR_TRANSITION] * 1000)
        else:
            fade = 0

        self.device.set_power(False, None, fade)

        self.update_later(fade)
        if fade < BULB_LATENCY:
            self.set_power(0)

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

        color_name = kwargs.pop(ATTR_COLOR_NAME, None)
        if color_name is not None:
            kwargs[ATTR_RGB_COLOR] = color_util.color_name_to_rgb(color_name)

        if ATTR_RGB_COLOR in kwargs:
            hue, saturation, brightness = \
                convert_rgb_to_hsv(kwargs[ATTR_RGB_COLOR])
            changed_color = True
        else:
            hue = self._hue
            saturation = self._sat
            brightness = self._bri

        if ATTR_XY_COLOR in kwargs:
            hue, saturation = color_util.color_xy_to_hs(*kwargs[ATTR_XY_COLOR])
            saturation = saturation * (BYTE_MAX + 1)
            changed_color = True

        # When color or temperature is set, use a default value for the other
        if ATTR_COLOR_TEMP in kwargs:
            kelvin = int(color_temperature_mired_to_kelvin(
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
            brightness = kwargs[ATTR_BRIGHTNESS] * (BYTE_MAX + 1)
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

        red, green, blue = colorsys.hsv_to_rgb(
            hue / SHORT_MAX, sat / SHORT_MAX, bri / SHORT_MAX)

        red = int(red * BYTE_MAX)
        green = int(green * BYTE_MAX)
        blue = int(blue * BYTE_MAX)

        _LOGGER.debug("set_color: %d %d %d %d [%d %d %d]",
                      hue, sat, bri, kel, red, green, blue)

        self._rgb = [red, green, blue]
