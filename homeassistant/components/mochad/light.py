"""Support for X10 dimmer over Mochad."""
import logging

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light, PLATFORM_SCHEMA)
from homeassistant.components import mochad
from homeassistant.const import (
    CONF_NAME, CONF_PLATFORM, CONF_DEVICES, CONF_ADDRESS)
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_BRIGHTNESS_LEVELS = 'brightness_levels'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PLATFORM): mochad.DOMAIN,
    CONF_DEVICES: [{
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_ADDRESS): cv.x10_address,
        vol.Optional(mochad.CONF_COMM_TYPE): cv.string,
        vol.Optional(CONF_BRIGHTNESS_LEVELS, default=32):
            vol.All(vol.Coerce(int), vol.In([32, 64, 256])),
    }]
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up X10 dimmers over a mochad controller."""
    devs = config.get(CONF_DEVICES)
    add_entities([MochadLight(
        hass, mochad.CONTROLLER.ctrl, dev) for dev in devs])
    return True


class MochadLight(Light):
    """Representation of a X10 dimmer over Mochad."""

    def __init__(self, hass, ctrl, dev):
        """Initialize a Mochad Light Device."""
        from pymochad import device

        self._controller = ctrl
        self._address = dev[CONF_ADDRESS]
        self._name = dev.get(
            CONF_NAME, 'x10_light_dev_{}'.format(self._address))
        self._comm_type = dev.get(mochad.CONF_COMM_TYPE, 'pl')
        self.light = device.Device(
            ctrl, self._address, comm_type=self._comm_type)
        self._brightness = 0
        self._state = self._get_device_status()
        self._brightness_levels = dev.get(CONF_BRIGHTNESS_LEVELS) - 1

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    def _get_device_status(self):
        """Get the status of the light from mochad."""
        with mochad.REQ_LOCK:
            status = self.light.get_status().rstrip()
        return status == 'on'

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def is_on(self):
        """Return true if the light is on."""
        return self._state

    @property
    def supported_features(self):
        """Return supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def assumed_state(self):
        """X10 devices are normally 1-way so we have to assume the state."""
        return True

    def _calculate_brightness_value(self, value):
        return int(value * (float(self._brightness_levels) / 255.0))

    def _adjust_brightness(self, brightness):
        if self._brightness > brightness:
            bdelta = self._brightness - brightness
            mochad_brightness = self._calculate_brightness_value(bdelta)
            self.light.send_cmd("dim {}".format(mochad_brightness))
            self._controller.read_data()
        elif self._brightness < brightness:
            bdelta = brightness - self._brightness
            mochad_brightness = self._calculate_brightness_value(bdelta)
            self.light.send_cmd("bright {}".format(mochad_brightness))
            self._controller.read_data()

    def turn_on(self, **kwargs):
        """Send the command to turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        with mochad.REQ_LOCK:
            if self._brightness_levels > 32:
                out_brightness = self._calculate_brightness_value(brightness)
                self.light.send_cmd('xdim {}'.format(out_brightness))
                self._controller.read_data()
            else:
                self.light.send_cmd("on")
                self._controller.read_data()
                # There is no persistence for X10 modules so a fresh on command
                # will be full brightness
                if self._brightness == 0:
                    self._brightness = 255
                self._adjust_brightness(brightness)
        self._brightness = brightness
        self._state = True

    def turn_off(self, **kwargs):
        """Send the command to turn the light on."""
        with mochad.REQ_LOCK:
            self.light.send_cmd('off')
            self._controller.read_data()
            # There is no persistence for X10 modules so we need to prepare
            # to track a fresh on command will full brightness
            if self._brightness_levels == 31:
                self._brightness = 0
        self._state = False
