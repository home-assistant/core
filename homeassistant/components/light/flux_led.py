"""
Support for Flux lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.flux_led/
"""
import logging
import socket
import random

import voluptuous as vol

from homeassistant.const import CONF_DEVICES, CONF_NAME, CONF_PROTOCOL
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_HS_COLOR, ATTR_EFFECT, EFFECT_COLORLOOP,
    EFFECT_RANDOM, SUPPORT_BRIGHTNESS, SUPPORT_EFFECT,
    SUPPORT_COLOR, Light, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

REQUIREMENTS = ['flux_led==0.21']

_LOGGER = logging.getLogger(__name__)

CONF_AUTOMATIC_ADD = 'automatic_add'
ATTR_MODE = 'mode'

DOMAIN = 'flux_led'

SUPPORT_FLUX_LED = (SUPPORT_BRIGHTNESS | SUPPORT_EFFECT |
                    SUPPORT_COLOR)

MODE_RGB = 'rgb'
MODE_RGBW = 'rgbw'

# List of supported effects which aren't already declared in LIGHT
EFFECT_RED_FADE = 'red_fade'
EFFECT_GREEN_FADE = 'green_fade'
EFFECT_BLUE_FADE = 'blue_fade'
EFFECT_YELLOW_FADE = 'yellow_fade'
EFFECT_CYAN_FADE = 'cyan_fade'
EFFECT_PURPLE_FADE = 'purple_fade'
EFFECT_WHITE_FADE = 'white_fade'
EFFECT_RED_GREEN_CROSS_FADE = 'rg_cross_fade'
EFFECT_RED_BLUE_CROSS_FADE = 'rb_cross_fade'
EFFECT_GREEN_BLUE_CROSS_FADE = 'gb_cross_fade'
EFFECT_COLORSTROBE = 'colorstrobe'
EFFECT_RED_STROBE = 'red_strobe'
EFFECT_GREEN_STROBE = 'green_strobe'
EFFECT_BLUE_STROBE = 'blue_strobe'
EFFECT_YELLOW_STROBE = 'yellow_strobe'
EFFECT_CYAN_STROBE = 'cyan_strobe'
EFFECT_PURPLE_STROBE = 'purple_strobe'
EFFECT_WHITE_STROBE = 'white_strobe'
EFFECT_COLORJUMP = 'colorjump'

EFFECT_MAP = {
    EFFECT_COLORLOOP:             0x25,
    EFFECT_RED_FADE:              0x26,
    EFFECT_GREEN_FADE:            0x27,
    EFFECT_BLUE_FADE:             0x28,
    EFFECT_YELLOW_FADE:           0x29,
    EFFECT_CYAN_FADE:             0x2a,
    EFFECT_PURPLE_FADE:           0x2b,
    EFFECT_WHITE_FADE:            0x2c,
    EFFECT_RED_GREEN_CROSS_FADE:  0x2d,
    EFFECT_RED_BLUE_CROSS_FADE:   0x2e,
    EFFECT_GREEN_BLUE_CROSS_FADE: 0x2f,
    EFFECT_COLORSTROBE:           0x30,
    EFFECT_RED_STROBE:            0x31,
    EFFECT_GREEN_STROBE:          0x32,
    EFFECT_BLUE_STROBE:            0x33,
    EFFECT_YELLOW_STROBE:         0x34,
    EFFECT_CYAN_STROBE:           0x35,
    EFFECT_PURPLE_STROBE:         0x36,
    EFFECT_WHITE_STROBE:          0x37,
    EFFECT_COLORJUMP:             0x38
}

FLUX_EFFECT_LIST = [
    EFFECT_RANDOM,
    ] + list(EFFECT_MAP)

DEVICE_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(ATTR_MODE, default=MODE_RGBW):
        vol.All(cv.string, vol.In([MODE_RGBW, MODE_RGB])),
    vol.Optional(CONF_PROTOCOL):
        vol.All(cv.string, vol.In(['ledenet'])),
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA},
    vol.Optional(CONF_AUTOMATIC_ADD, default=False):  cv.boolean,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Flux lights."""
    import flux_led
    lights = []
    light_ips = []

    for ipaddr, device_config in config.get(CONF_DEVICES, {}).items():
        device = {}
        device['name'] = device_config[CONF_NAME]
        device['ipaddr'] = ipaddr
        device[CONF_PROTOCOL] = device_config.get(CONF_PROTOCOL)
        device[ATTR_MODE] = device_config[ATTR_MODE]
        light = FluxLight(device)
        lights.append(light)
        light_ips.append(ipaddr)

    if not config.get(CONF_AUTOMATIC_ADD, False):
        add_devices(lights, True)
        return

    # Find the bulbs on the LAN
    scanner = flux_led.BulbScanner()
    scanner.scan(timeout=10)
    for device in scanner.getBulbInfo():
        ipaddr = device['ipaddr']
        if ipaddr in light_ips:
            continue
        device['name'] = '{} {}'.format(device['id'], ipaddr)
        device[ATTR_MODE] = MODE_RGBW
        device[CONF_PROTOCOL] = None
        light = FluxLight(device)
        lights.append(light)

    add_devices(lights, True)


class FluxLight(Light):
    """Representation of a Flux light."""

    def __init__(self, device):
        """Initialize the light."""
        self._name = device['name']
        self._ipaddr = device['ipaddr']
        self._protocol = device[CONF_PROTOCOL]
        self._mode = device[ATTR_MODE]
        self._bulb = None
        self._error_reported = False

    def _connect(self):
        """Connect to Flux light."""
        import flux_led

        self._bulb = flux_led.WifiLedBulb(self._ipaddr, timeout=5)
        if self._protocol:
            self._bulb.setProtocol(self._protocol)

        # After bulb object is created the status is updated. We can
        # now set the correct mode if it was not explicitly defined.
        if not self._mode:
            if self._bulb.rgbwcapable:
                self._mode = MODE_RGBW
            else:
                self._mode = MODE_RGB

    def _disconnect(self):
        """Disconnect from Flux light."""
        self._bulb = None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._bulb is not None

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
    def hs_color(self):
        """Return the color property."""
        return color_util.color_RGB_to_hs(*self._bulb.getRgb())

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_FLUX_LED

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return FLUX_EFFECT_LIST

    def turn_on(self, **kwargs):
        """Turn the specified or all lights on."""
        if not self.is_on:
            self._bulb.turnOn()

        hs_color = kwargs.get(ATTR_HS_COLOR)

        if hs_color:
            rgb = color_util.color_hs_to_RGB(*hs_color)
        else:
            rgb = None

        brightness = kwargs.get(ATTR_BRIGHTNESS)
        effect = kwargs.get(ATTR_EFFECT)

        if rgb is not None and brightness is not None:
            self._bulb.setRgb(*tuple(rgb), brightness=brightness)
        elif rgb is not None:
            self._bulb.setRgb(*tuple(rgb))
        elif brightness is not None:
            if self._mode == MODE_RGBW:
                self._bulb.setWarmWhite255(brightness)
            elif self._mode == MODE_RGB:
                (red, green, blue) = self._bulb.getRgb()
                self._bulb.setRgb(red, green, blue, brightness=brightness)
        elif effect == EFFECT_RANDOM:
            self._bulb.setRgb(random.randint(0, 255),
                              random.randint(0, 255),
                              random.randint(0, 255))
        elif effect in EFFECT_MAP:
            self._bulb.setPresetPattern(EFFECT_MAP[effect], 50)

    def turn_off(self, **kwargs):
        """Turn the specified or all lights off."""
        self._bulb.turnOff()

    def update(self):
        """Synchronize state with bulb."""
        if not self.available:
            try:
                self._connect()
                self._error_reported = False
            except socket.error:
                self._disconnect()
                if not self._error_reported:
                    _LOGGER.warning("Failed to connect to bulb %s, %s",
                                    self._ipaddr, self._name)
                    self._error_reported = True
                return

        self._bulb.update_state(retry=2)
