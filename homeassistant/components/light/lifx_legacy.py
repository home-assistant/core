"""
Support for the LIFX platform that implements lights.

This is a legacy platform, included because the current lifx platform does
not yet support Windows.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.lifx/
"""
import logging

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_HS_COLOR, ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_COLOR,
    SUPPORT_TRANSITION, Light, PLATFORM_SCHEMA)
from homeassistant.helpers.event import track_time_change
from homeassistant.util.color import (
    color_temperature_mired_to_kelvin, color_temperature_kelvin_to_mired)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['liffylights==0.9.4']

BYTE_MAX = 255

CONF_BROADCAST = 'broadcast'
CONF_SERVER = 'server'

SHORT_MAX = 65535

TEMP_MAX = 9000
TEMP_MAX_HASS = 500
TEMP_MIN = 2500
TEMP_MIN_HASS = 154

SUPPORT_LIFX = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_COLOR |
                SUPPORT_TRANSITION)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SERVER): cv.string,
    vol.Optional(CONF_BROADCAST): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the LIFX platform."""
    server_addr = config.get(CONF_SERVER)
    broadcast_addr = config.get(CONF_BROADCAST)

    lifx_library = LIFX(add_devices, server_addr, broadcast_addr)

    # Register our poll service
    track_time_change(hass, lifx_library.poll, second=[10, 40])

    lifx_library.probe()


class LIFX(object):
    """Representation of a LIFX light."""

    def __init__(self, add_devices_callback, server_addr=None,
                 broadcast_addr=None):
        """Initialize the light."""
        import liffylights

        self._devices = []

        self._add_devices_callback = add_devices_callback

        self._liffylights = liffylights.LiffyLights(
            self.on_device, self.on_power, self.on_color, server_addr,
            broadcast_addr)

    def find_bulb(self, ipaddr):
        """Search for bulbs."""
        bulb = None
        for device in self._devices:
            if device.ipaddr == ipaddr:
                bulb = device
                break
        return bulb

    def on_device(self, ipaddr, name, power, hue, sat, bri, kel):
        """Initialize the light."""
        bulb = self.find_bulb(ipaddr)

        if bulb is None:
            _LOGGER.debug("new bulb %s %s %d %d %d %d %d",
                          ipaddr, name, power, hue, sat, bri, kel)
            bulb = LIFXLight(
                self._liffylights, ipaddr, name, power, hue, sat, bri, kel)
            self._devices.append(bulb)
            self._add_devices_callback([bulb])
        else:
            _LOGGER.debug("update bulb %s %s %d %d %d %d %d",
                          ipaddr, name, power, hue, sat, bri, kel)
            bulb.set_power(power)
            bulb.set_color(hue, sat, bri, kel)
            bulb.schedule_update_ha_state()

    def on_color(self, ipaddr, hue, sat, bri, kel):
        """Initialize the light."""
        bulb = self.find_bulb(ipaddr)

        if bulb is not None:
            bulb.set_color(hue, sat, bri, kel)
            bulb.schedule_update_ha_state()

    def on_power(self, ipaddr, power):
        """Initialize the light."""
        bulb = self.find_bulb(ipaddr)

        if bulb is not None:
            bulb.set_power(power)
            bulb.schedule_update_ha_state()

    def poll(self, now):
        """Set up polling for the light."""
        self.probe()

    def probe(self, address=None):
        """Probe the light."""
        self._liffylights.probe(address)


class LIFXLight(Light):
    """Representation of a LIFX light."""

    def __init__(self, liffy, ipaddr, name, power, hue, saturation, brightness,
                 kelvin):
        """Initialize the light."""
        _LOGGER.debug("LIFXLight: %s %s", ipaddr, name)

        self._liffylights = liffy
        self._ip = ipaddr
        self.set_name(name)
        self.set_power(power)
        self.set_color(hue, saturation, brightness, kelvin)

    @property
    def should_poll(self):
        """No polling needed for LIFX light."""
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def ipaddr(self):
        """Return the IP address of the device."""
        return self._ip

    @property
    def hs_color(self):
        """Return the hs value."""
        return (self._hue / 65535 * 360, self._sat / 65535 * 100)

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
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_LIFX

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if ATTR_TRANSITION in kwargs:
            fade = int(kwargs[ATTR_TRANSITION] * 1000)
        else:
            fade = 0

        if ATTR_HS_COLOR in kwargs:
            hue, saturation = kwargs[ATTR_HS_COLOR]
            hue = hue / 360 * 65535
            saturation = saturation / 100 * 65535
        else:
            hue = self._hue
            saturation = self._sat

        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS] * (BYTE_MAX + 1)
        else:
            brightness = self._bri

        if ATTR_COLOR_TEMP in kwargs:
            kelvin = int(color_temperature_mired_to_kelvin(
                kwargs[ATTR_COLOR_TEMP]))
        else:
            kelvin = self._kel

        _LOGGER.debug("turn_on: %s (%d) %d %d %d %d %d",
                      self._ip, self._power,
                      hue, saturation, brightness, kelvin, fade)

        if self._power == 0:
            self._liffylights.set_color(self._ip, hue, saturation,
                                        brightness, kelvin, 0)
            self._liffylights.set_power(self._ip, 65535, fade)
        else:
            self._liffylights.set_color(self._ip, hue, saturation,
                                        brightness, kelvin, fade)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        if ATTR_TRANSITION in kwargs:
            fade = int(kwargs[ATTR_TRANSITION] * 1000)
        else:
            fade = 0

        _LOGGER.debug("turn_off: %s %d", self._ip, fade)
        self._liffylights.set_power(self._ip, 0, fade)

    def set_name(self, name):
        """Set name of the light."""
        self._name = name

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
