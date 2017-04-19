"""
Support for the LIFX platform that implements lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.lifx/
"""
import colorsys
import logging
import asyncio
import sys
import random
from os import path
from functools import partial
from datetime import timedelta
import async_timeout

import voluptuous as vol

from homeassistant.components.light import (
    Light, DOMAIN, PLATFORM_SCHEMA, ATTR_BRIGHTNESS, ATTR_COLOR_NAME,
    ATTR_RGB_COLOR, ATTR_COLOR_TEMP, ATTR_TRANSITION, ATTR_EFFECT,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_RGB_COLOR,
    SUPPORT_TRANSITION, SUPPORT_EFFECT)
from homeassistant.util.color import (
    color_temperature_mired_to_kelvin, color_temperature_kelvin_to_mired)
from homeassistant import util
from homeassistant.core import callback
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (ATTR_ENTITY_ID)
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.service import extract_entity_ids
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['aiolifx==0.4.4']

UDP_BROADCAST_PORT = 56700

# Delay (in ms) expected for changes to take effect in the physical bulb
BULB_LATENCY = 500

CONF_SERVER = 'server'

SERVICE_EFFECT_BREATHE = 'lifx_effect_breathe'
SERVICE_EFFECT_PULSE = 'lifx_effect_pulse'
SERVICE_EFFECT_COLORLOOP = 'lifx_effect_colorloop'

ATTR_POWER_ON = 'power_on'
ATTR_PERIOD = 'period'
ATTR_CYCLES = 'cycles'
ATTR_SPREAD = 'spread'
ATTR_CHANGE = 'change'
ATTR_HSBK = 'hsbk'

# aiolifx waveform modes
WAVEFORM_SINE = 1
WAVEFORM_PULSE = 4

# The least visible color setting
HSBK_NO_COLOR = [0, 65535, 0, 2500]

BYTE_MAX = 255
SHORT_MAX = 65535

SUPPORT_LIFX = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_RGB_COLOR |
                SUPPORT_TRANSITION | SUPPORT_EFFECT)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SERVER, default='0.0.0.0'): cv.string,
})

LIFX_EFFECT_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_POWER_ON, default=True): cv.boolean,
})

LIFX_EFFECT_BREATHE_SCHEMA = LIFX_EFFECT_SCHEMA.extend({
    ATTR_BRIGHTNESS: vol.All(vol.Coerce(int), vol.Clamp(min=0, max=255)),
    ATTR_COLOR_NAME: cv.string,
    ATTR_RGB_COLOR: vol.All(vol.ExactSequence((cv.byte, cv.byte, cv.byte)),
                            vol.Coerce(tuple)),
    vol.Optional(ATTR_PERIOD, default=1.0): vol.All(vol.Coerce(float),
                                                    vol.Range(min=0.05)),
    vol.Optional(ATTR_CYCLES, default=1.0): vol.All(vol.Coerce(float),
                                                    vol.Range(min=1)),
})

LIFX_EFFECT_PULSE_SCHEMA = LIFX_EFFECT_BREATHE_SCHEMA

LIFX_EFFECT_COLORLOOP_SCHEMA = LIFX_EFFECT_SCHEMA.extend({
    ATTR_BRIGHTNESS: vol.All(vol.Coerce(int), vol.Clamp(min=0, max=255)),
    vol.Optional(ATTR_PERIOD, default=60): vol.All(vol.Coerce(float),
                                                   vol.Clamp(min=1)),
    vol.Optional(ATTR_CHANGE, default=20): vol.All(vol.Coerce(float),
                                                   vol.Clamp(min=0, max=360)),
    vol.Optional(ATTR_SPREAD, default=30): vol.All(vol.Coerce(float),
                                                   vol.Clamp(min=0, max=360)),
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the LIFX platform."""
    import aiolifx

    if sys.platform == 'win32':
        _LOGGER.warning('The lifx platform is known to not work on Windows. '
                        'Consider using the lifx_legacy platform instead.')

    server_addr = config.get(CONF_SERVER)

    lifx_manager = LIFXManager(hass, async_add_devices)

    coro = hass.loop.create_datagram_endpoint(
        partial(aiolifx.LifxDiscovery, hass.loop, lifx_manager),
        local_addr=(server_addr, UDP_BROADCAST_PORT))

    hass.async_add_job(coro)

    @asyncio.coroutine
    def async_service_handle(service):
        """Internal func for applying a service."""
        entity_ids = extract_entity_ids(hass, service)
        if entity_ids:
            devices = [entity for entity in lifx_manager.entities.values()
                       if entity.entity_id in entity_ids]
        else:
            devices = lifx_manager.entities.values()

        yield from start_effect(hass, devices, service.service, **service.data)

    descriptions = load_yaml_config_file(
        path.join(path.dirname(__file__), 'services.yaml'))

    hass.services.async_register(
        DOMAIN, SERVICE_EFFECT_BREATHE, async_service_handle,
        descriptions.get(SERVICE_EFFECT_BREATHE),
        schema=LIFX_EFFECT_BREATHE_SCHEMA)

    hass.services.async_register(
        DOMAIN, SERVICE_EFFECT_PULSE, async_service_handle,
        descriptions.get(SERVICE_EFFECT_PULSE),
        schema=LIFX_EFFECT_PULSE_SCHEMA)

    hass.services.async_register(
        DOMAIN, SERVICE_EFFECT_COLORLOOP, async_service_handle,
        descriptions.get(SERVICE_EFFECT_COLORLOOP),
        schema=LIFX_EFFECT_COLORLOOP_SCHEMA)

    return True


@asyncio.coroutine
def start_effect(hass, devices, service, **data):
    """Start a light effect."""
    for light in devices:
        yield from light.stop_effect()

    if service in SERVICE_EFFECT_BREATHE:
        effect = LIFXEffectBreathe(hass, devices)
    elif service in SERVICE_EFFECT_PULSE:
        effect = LIFXEffectPulse(hass, devices)
    elif service == SERVICE_EFFECT_COLORLOOP:
        effect = LIFXEffectColorloop(hass, devices)

    hass.async_add_job(effect.async_perform(**data))


class LIFXManager(object):
    """Representation of all known LIFX entities."""

    def __init__(self, hass, async_add_devices):
        """Initialize the light."""
        self.entities = {}
        self.hass = hass
        self.async_add_devices = async_add_devices

    @callback
    def register(self, device):
        """Callback for newly detected bulb."""
        if device.mac_addr in self.entities:
            entity = self.entities[device.mac_addr]
            entity.device = device
            _LOGGER.debug("%s register AGAIN", entity.who)
            self.hass.async_add_job(entity.async_update_ha_state())
        else:
            _LOGGER.debug("%s register NEW", device.ip_addr)
            device.get_color(self.ready)

    @callback
    def ready(self, device, msg):
        """Callback that adds the device once all data is retrieved."""
        entity = LIFXLight(device)
        _LOGGER.debug("%s register READY", entity.who)
        self.entities[device.mac_addr] = entity
        self.async_add_devices([entity])

    @callback
    def unregister(self, device):
        """Callback for disappearing bulb."""
        if device.mac_addr in self.entities:
            entity = self.entities[device.mac_addr]
            _LOGGER.debug("%s unregister", entity.who)
            entity.device = None
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
        """Callback that aiolifx invokes when the response is received."""
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
        self.blocker = None
        self.effect_data = None
        self.postponed_update = None
        self._name = device.label
        self.set_power(device.power_level)
        self.set_color(*device.color)

    @property
    def available(self):
        """Return the availability of the device."""
        return self.device is not None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def who(self):
        """Return a string identifying the device."""
        if self.device:
            return self.device.ip_addr[0]
        else:
            return "(%s)" % self.name

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
    def is_on(self):
        """Return true if device is on."""
        _LOGGER.debug("is_on: %d", self._power)
        return self._power != 0

    @property
    def effect(self):
        """Return the currently running effect."""
        if self.effect_data is not None:
            return self.effect_data.effect.name
        else:
            return None

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_LIFX

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return [
            SERVICE_EFFECT_COLORLOOP,
            SERVICE_EFFECT_BREATHE,
            SERVICE_EFFECT_PULSE,
        ]

    @callback
    def update_after_transition(self, now):
        """Request new status after completion of the last transition."""
        self.postponed_update = None
        self.hass.async_add_job(self.async_update_ha_state(force_refresh=True))

    @callback
    def unblock_updates(self, now):
        """Allow async_update after the new state has settled on the bulb."""
        self.blocker = None
        self.hass.async_add_job(self.async_update_ha_state(force_refresh=True))

    def update_later(self, when):
        """Block immediate update requests and schedule one for later."""
        if self.blocker:
            self.blocker()
        self.blocker = async_track_point_in_utc_time(
            self.hass, self.unblock_updates,
            util.dt.utcnow() + timedelta(milliseconds=BULB_LATENCY))

        if self.postponed_update:
            self.postponed_update()
        if when > BULB_LATENCY:
            self.postponed_update = async_track_point_in_utc_time(
                self.hass, self.update_after_transition,
                util.dt.utcnow() + timedelta(milliseconds=when+BULB_LATENCY))

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the device on."""
        yield from self.stop_effect()

        if ATTR_EFFECT in kwargs:
            yield from self.default_effect(**kwargs)
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
        if self.available and self.blocker is None:
            yield from self.refresh_state()

    @asyncio.coroutine
    def default_effect(self, **kwargs):
        """Start an effect with default (or random) parameters."""
        service = kwargs[ATTR_EFFECT]
        data = {
            ATTR_ENTITY_ID: self.entity_id,
        }

        if service in (SERVICE_EFFECT_BREATHE, SERVICE_EFFECT_PULSE):
            data[ATTR_RGB_COLOR] = [
                random.randint(100, 255),
                random.randint(100, 255),
                random.randint(100, 255),
            ]

        yield from self.hass.services.async_call(DOMAIN, service, data)

    @asyncio.coroutine
    def stop_effect(self):
        """Stop the currently running effect (if any)."""
        if self.effect_data:
            yield from self.effect_data.effect.async_restore(self)

    @asyncio.coroutine
    def refresh_state(self):
        """Ask the device about its current state and update our copy."""
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

        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS] * (BYTE_MAX + 1)
            changed_color = True
        else:
            brightness = self._bri

        if ATTR_COLOR_TEMP in kwargs:
            kelvin = int(color_temperature_mired_to_kelvin(
                kwargs[ATTR_COLOR_TEMP]))
            changed_color = True
        else:
            kelvin = self._kel

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

        red, green, blue = colorsys.hsv_to_rgb(hue / SHORT_MAX,
                                               sat / SHORT_MAX,
                                               bri / SHORT_MAX)

        red = int(red * BYTE_MAX)
        green = int(green * BYTE_MAX)
        blue = int(blue * BYTE_MAX)

        _LOGGER.debug("set_color: %d %d %d %d [%d %d %d]",
                      hue, sat, bri, kel, red, green, blue)

        self._rgb = [red, green, blue]


class LIFXEffectData(object):
    """Structure describing a running effect."""

    def __init__(self, effect, power, color):
        """Initialize data structure."""
        self.effect = effect
        self.power = power
        self.color = color


class LIFXEffect(object):
    """Representation of a light effect running on a number of lights."""

    def __init__(self, hass, lights):
        """Initialize the effect."""
        self.hass = hass
        self.lights = lights

    @asyncio.coroutine
    def async_perform(self, **kwargs):
        """Do common setup and play the effect."""
        yield from self.async_setup(**kwargs)
        yield from self.async_play(**kwargs)

    @asyncio.coroutine
    def async_setup(self, **kwargs):
        """Prepare all lights for the effect."""
        for light in self.lights:
            yield from light.refresh_state()
            if not light.device:
                self.lights.remove(light)
            else:
                light.effect_data = LIFXEffectData(
                    self, light.is_on, light.device.color)

                # Temporarily turn on power for the effect to be visible
                if kwargs[ATTR_POWER_ON] and not light.is_on:
                    light.device.set_color(HSBK_NO_COLOR)
                    light.device.set_power(True)

    # pylint: disable=no-self-use
    @asyncio.coroutine
    def async_play(self, **kwargs):
        """Play the effect."""
        yield None

    @asyncio.coroutine
    def async_restore(self, light):
        """Restore to the original state (if we are still running)."""
        if light.effect_data:
            if light.effect_data.effect == self:
                if light.device and not light.effect_data.power:
                    light.device.set_power(False)
                    yield from asyncio.sleep(BULB_LATENCY/1000)
                if light.device:
                    light.device.set_color(light.effect_data.color)
                    yield from asyncio.sleep(BULB_LATENCY/1000)
                light.effect_data = None
            self.lights.remove(light)


class LIFXEffectBreathe(LIFXEffect):
    """Representation of a breathe effect."""

    def __init__(self, hass, lights):
        """Initialize the breathe effect."""
        super(LIFXEffectBreathe, self).__init__(hass, lights)
        self.name = SERVICE_EFFECT_BREATHE
        self.waveform = WAVEFORM_SINE

    @asyncio.coroutine
    def async_play(self, **kwargs):
        """Play the effect on all lights."""
        for light in self.lights:
            self.hass.async_add_job(self.async_light_play(light, **kwargs))

    @asyncio.coroutine
    def async_light_play(self, light, **kwargs):
        """Play a light effect on the bulb."""
        period = kwargs[ATTR_PERIOD]
        cycles = kwargs[ATTR_CYCLES]
        hsbk, _ = light.find_hsbk(**kwargs)

        # Start the effect
        args = {
            'transient': 1,
            'color': hsbk,
            'period': int(period*1000),
            'cycles': cycles,
            'duty_cycle': 0,
            'waveform': self.waveform,
        }
        light.device.set_waveform(args)

        # Wait for completion and restore the initial state
        yield from asyncio.sleep(period*cycles)
        yield from self.async_restore(light)


class LIFXEffectPulse(LIFXEffectBreathe):
    """Representation of a pulse effect."""

    def __init__(self, hass, lights):
        """Initialize the pulse effect."""
        super(LIFXEffectPulse, self).__init__(hass, lights)
        self.name = SERVICE_EFFECT_PULSE
        self.waveform = WAVEFORM_PULSE


class LIFXEffectColorloop(LIFXEffect):
    """Representation of a colorloop effect."""

    def __init__(self, hass, lights):
        """Initialize the colorloop effect."""
        super(LIFXEffectColorloop, self).__init__(hass, lights)
        self.name = SERVICE_EFFECT_COLORLOOP

    @asyncio.coroutine
    def async_play(self, **kwargs):
        """Play the effect on all lights."""
        period = kwargs[ATTR_PERIOD]
        spread = kwargs[ATTR_SPREAD]
        change = kwargs[ATTR_CHANGE]
        direction = 1 if random.randint(0, 1) else -1

        # Random start
        hue = random.randint(0, 360)

        while self.lights:
            hue = (hue + direction*change) % 360

            random.shuffle(self.lights)
            lhue = hue

            transition = int(1000 * random.uniform(period/2, period))
            for light in self.lights:
                if spread > 0:
                    transition = int(1000 * random.uniform(period/2, period))

                if ATTR_BRIGHTNESS in kwargs:
                    brightness = int(65535/255*kwargs[ATTR_BRIGHTNESS])
                else:
                    brightness = light.effect_data.color[2]

                hsbk = [
                    int(65535/359*lhue),
                    int(random.uniform(0.8, 1.0)*65535),
                    brightness,
                    4000,
                ]
                light.device.set_color(hsbk, None, transition)

                # Adjust the next light so the full spread is used
                if len(self.lights) > 1:
                    lhue = (lhue + spread/(len(self.lights)-1)) % 360

            yield from asyncio.sleep(period)
