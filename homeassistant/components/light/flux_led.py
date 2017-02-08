"""
Support for Flux lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.flux_led/
"""
from datetime import timedelta
from functools import partial
import logging
import random
import socket

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_EFFECT, ATTR_RGB_COLOR, ATTR_TRANSITION,
    EFFECT_RANDOM, PLATFORM_SCHEMA, SUPPORT_BRIGHTNESS, SUPPORT_EFFECT,
    SUPPORT_RGB_COLOR, SUPPORT_TRANSITION, Light)
from homeassistant.const import CONF_DEVICES, CONF_NAME, CONF_PROTOCOL
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['flux_led==0.13']

_LOGGER = logging.getLogger(__name__)

CONF_AUTOMATIC_ADD = 'automatic_add'
ATTR_MODE = 'mode'

DOMAIN = 'flux_led'

SUPPORT_FLUX_LED = (SUPPORT_BRIGHTNESS | SUPPORT_EFFECT |
                    SUPPORT_RGB_COLOR | SUPPORT_TRANSITION)

MODE_RGB = 'rgb'
MODE_RGBW = 'rgbw'

TRANSITION_TYPE = 'gradual'

DEVICE_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(ATTR_MODE, default=MODE_RGBW):
        vol.All(cv.string, vol.In([MODE_RGBW, MODE_RGB])),
    vol.Optional(CONF_PROTOCOL, default=None):
        vol.All(cv.string, vol.In(['ledenet'])),
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA},
    vol.Optional(CONF_AUTOMATIC_ADD, default=False):  cv.boolean,
})

# maximum possible transition time
MAX_TRANSITION_TIME = timedelta(seconds=30)

STOP_EXTRA_DELAY = timedelta(seconds=1)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Flux lights."""
    import flux_led
    lights = []
    light_ips = []

    for ipaddr, device_config in config.get(CONF_DEVICES, {}).items():
        device = {}
        device['name'] = device_config[CONF_NAME]
        device['ipaddr'] = ipaddr
        device[CONF_PROTOCOL] = device_config[CONF_PROTOCOL]
        device[ATTR_MODE] = device_config[ATTR_MODE]
        light = FluxLight(device, hass)
        if light.is_valid:
            lights.append(light)
            light_ips.append(ipaddr)

    if discovery_info:
        device = {}
        # discovery_info: ip address,device id,device type
        device['ipaddr'] = discovery_info[0]
        device['name'] = discovery_info[1]
        # As we don't know protocol and mode set to none to autodetect.
        device[CONF_PROTOCOL] = None
        device[ATTR_MODE] = None

        light = FluxLight(device)
        if light.is_valid:
            lights.append(light)
            light_ips.append(device['ipaddr'])

    if not config.get(CONF_AUTOMATIC_ADD, False):
        add_devices(lights)
        return

    # Find the bulbs on the LAN
    scanner = flux_led.BulbScanner()
    scanner.scan(timeout=10)
    for device in scanner.getBulbInfo():
        ipaddr = device['ipaddr']
        if ipaddr in light_ips:
            continue
        device['name'] = device['id'] + " " + ipaddr
        device[ATTR_MODE] = 'rgbw'
        device[CONF_PROTOCOL] = None
        light = FluxLight(device, hass)
        if light.is_valid:
            lights.append(light)
            light_ips.append(ipaddr)

    add_devices(lights)


class FluxLight(Light):
    """Representation of a Flux light."""

    previous_color_rgb = None
    previous_brightness = None
    transition_stop_handle = None

    def __init__(self, device, hass=None):
        """Initialize the light."""
        import flux_led

        self._name = device['name']
        self._ipaddr = device['ipaddr']
        self._protocol = device[CONF_PROTOCOL]
        self._mode = device[ATTR_MODE]
        self.is_valid = True
        self._bulb = None
        self.hass = hass
        try:
            self._bulb = flux_led.WifiLedBulb(self._ipaddr)
            if self._protocol:
                self._bulb.setProtocol(self._protocol)

            # After bulb object is created the status is updated. We can
            # now set the correct mode if it was not explicitly defined.
            if not self._mode:
                if self._bulb.rgbwcapable:
                    self._mode = MODE_RGBW
                else:
                    self._mode = MODE_RGB

        except socket.error:
            self.is_valid = False
            _LOGGER.error(
                "Failed to connect to bulb %s, %s", self._ipaddr, self._name)

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return "{}.{}".format(self.__class__, self._ipaddr)

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._bulb.isOn()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._bulb.brightness

    @property
    def rgb_color(self):
        """Return the color property."""
        return self._bulb.getRgb()

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_FLUX_LED

    def turn_on(self, **kwargs):
        """Turn the specified or all lights on."""
        # Cancel scheduled callback of fading action.
        if self.transition_stop_handle:
            self.transition_stop_handle.cancel()

        # If light was previously faded to black, restore previous color.
        if self.previous_brightness or self.previous_color_rgb:
            kwargs[ATTR_BRIGHTNESS] = self.previous_brightness
            kwargs[ATTR_RGB_COLOR] = self.previous_color_rgb
            self.previous_brightness = None
            self.previous_color_rgb = None

        if ATTR_TRANSITION in kwargs:
            # if light is not on assume the user wants
            # to transition from black to the new color
            if not self.is_on:
                self._bulb.turnOn()
                self._bulb.setRgb(0, 0, 0)

            self.set_color_transition(**kwargs)
        else:
            if not self.is_on:
                self._bulb.turnOn()

            self.set_color(**kwargs)

            # notify UI of change when turned on without transition
            self.schedule_update_ha_state(force_refresh=True)

    def set_color_transition(self, **kwargs):
        """Set a color transition for light."""

        from flux_led import utils

        to_rgb = list(kwargs.get(ATTR_RGB_COLOR))

        # flux_led support integer delay from 1-30 seconds
        transition = timedelta(seconds=kwargs[ATTR_TRANSITION])
        transition_time = min(transition, MAX_TRANSITION_TIME)
        if transition != transition_time:
            _LOGGER.warning('Requested transition time (%ss) '
                            'exceeds supported maximum (%ss)',
                            transition, transition_time)
        transition_speed = utils.delayToSpeed(transition_time.seconds)

        # Flux led support transitioning between 16 colors and repeats
        # the cycle after completion. Fading starts with the current color.
        # This fills the entire transition cycle with the 'to' color. This
        # gives us enough time to execute a transition stop after a delay.
        # Set a custom color pattern function into the led controller and
        # execute it.
        self._bulb.setCustomPattern(
            [to_rgb] * 16,
            transition_speed,
            TRANSITION_TYPE
        )

        # Function to stop transition by turning light on to desired color.
        kwargs_no_transition = kwargs.copy()
        del kwargs_no_transition['transition']
        stop_transition = partial(self.turn_on, **kwargs_no_transition)

        # Schedule a callback to turn on the bulb at the requested color,
        # effectively cancelling the custom color pattern. Since the color
        # pattern continuously cycles between 16 of the same color this is
        # strictly not needed, but it the nice thing to do
        self.transition_stop_handle = self.hass.loop.call_later(
            (transition_time + STOP_EXTRA_DELAY).seconds,
            stop_transition
        )

    def set_color(self, **kwargs):
        """Set the color for light."""
        rgb = kwargs.get(ATTR_RGB_COLOR)
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        effect = kwargs.get(ATTR_EFFECT)
        if rgb is not None and brightness is not None:
            self._bulb.setRgb(*tuple(rgb), brightness=brightness)
        elif rgb is not None:
            self._bulb.setRgb(*tuple(rgb))
        elif brightness is not None:
            if self._mode == 'rgbw':
                self._bulb.setWarmWhite255(brightness)
            elif self._mode == 'rgb':
                (red, green, blue) = self._bulb.getRgb()
                self._bulb.setRgb(red, green, blue, brightness=brightness)
        elif effect == EFFECT_RANDOM:
            self._bulb.setRgb(random.randrange(0, 255),
                              random.randrange(0, 255),
                              random.randrange(0, 255))

    def turn_off(self, **kwargs):
        """Turn the specified or all lights off."""

        # Cancel scheduled callback of fading action.
        if self.transition_stop_handle:
            self.transition_stop_handle.cancel()

        if ATTR_TRANSITION in kwargs:
            self.turn_off_transition(**kwargs)
        else:
            self._bulb.turnOff()

    def turn_off_transition(self, **kwargs):
        """Turn of light by fading to black."""

        from flux_led import utils

        # Remember the current color, this is used later when
        # the light is turned back on. Normal on/off behaviour of
        # this controller is to turn on with the color it was turned
        # of. This allows to maintain that behaviour when fading out.
        self.previous_color_rgb = self.rgb_color
        self.previous_brightness = self.brightness

        # flux_led support integer delay from 1-30 seconds
        transition = kwargs[ATTR_TRANSITION]
        transition_time = min(int(transition), MAX_TRANSITION_TIME.seconds)
        if transition != transition_time:
            _LOGGER.warning('Requested transition time (%ss) '
                            'exceeds supported maximum (%ss)',
                            transition, transition_time)
        transition_speed = utils.delayToSpeed(transition_time)

        # set a custom color pattern (see set_color_transition for details)
        self._bulb.setCustomPattern(
            [[0, 0, 0]] * 16,
            transition_speed,
            TRANSITION_TYPE
        )

        # turn off after transition has expired
        # (see turn_no_transition for details)
        self.transition_stop_handle = self.hass.loop.call_later(
            (transition_time + STOP_EXTRA_DELAY).seconds,
            self.turn_off
        )

    def update(self):
        """Synchronize state with bulb."""
        self._bulb.refreshState()
