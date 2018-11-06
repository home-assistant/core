"""Component for interfacing to Lutron Homeworks lights.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/homeworks/
"""
import logging
from homeassistant.components.homeworks import (
    HomeworksDevice, HOMEWORKS_CONTROLLER)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light, PLATFORM_SCHEMA)
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

DEPENDENCIES = ['homeworks']
REQUIREMENTS = ['pyhomeworks==0.0.1']

_LOGGER = logging.getLogger(__name__)

FADE_RATE = 2.

CONF_DIMMERS = 'dimmers'
CONF_ADDR = 'addr'
CONF_RATE = 'rate'

CV_FADE_RATE = vol.All(vol.Coerce(float), vol.Range(min=0, max=20))

DIMMER_SCHEMA = vol.Schema({
    vol.Required(CONF_ADDR): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_RATE, default=FADE_RATE): CV_FADE_RATE,
})
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DIMMERS): vol.All(cv.ensure_list, [DIMMER_SCHEMA])
})


def setup_platform(hass, config, add_entities, discover_info=None):
    """Set up the Homeworks lights."""
    controller = hass.data[HOMEWORKS_CONTROLLER]
    devs = []
    for dimmer in config.get(CONF_DIMMERS):
        dev = HomeworksLight(controller, dimmer[CONF_ADDR],
                             dimmer[CONF_NAME], dimmer[CONF_RATE])
        devs.append(dev)
    add_entities(devs, True)
    return True


class HomeworksLight(HomeworksDevice, Light):
    """Homeworks Light."""

    def __init__(self, controller, addr, name, rate):
        """Create device with Addr, name, and rate."""
        HomeworksDevice.__init__(self, controller, addr, name)
        self._rate = rate
        self._level = None
        self._controller.request_dimmer_level(addr)

    @property
    def supported_features(self):
        """Supported features."""
        return SUPPORT_BRIGHTNESS

    def turn_on(self, **kwargs):
        """Turn on the light."""
        if ATTR_BRIGHTNESS in kwargs:
            self.brightness = kwargs[ATTR_BRIGHTNESS]
        else:
            self.brightness = 255

    def turn_off(self, **kwargs):
        """Turn off the light."""
        self.brightness = 0

    @property
    def brightness(self):
        """Control the brightness."""
        return self._level

    @brightness.setter
    def brightness(self, level):
        self._controller.fade_dim(
            float((level*100.)/255.), self._rate,
            0, self._addr)
        self._level = level

    @property
    def device_state_attributes(self):
        """Supported attributes."""
        return {'Homeworks Address': self._addr}

    @property
    def is_on(self):
        """Is the light on/off."""
        return self._level != 0

    def callback(self, msg_type, values):
        """Process device specific messages."""
        from pyhomeworks.pyhomeworks import HW_LIGHT_CHANGED

        if msg_type == HW_LIGHT_CHANGED:
            self._level = int((values[1] * 255.)/100.)
            return True
        return False
