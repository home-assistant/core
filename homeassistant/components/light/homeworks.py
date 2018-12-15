"""Component for interfacing to Lutron Homeworks lights.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.homeworks/
"""
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect)
from homeassistant.components.homeworks import (
    HomeworksDevice, HOMEWORKS_CONTROLLER, ENTITY_SIGNAL)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light, PLATFORM_SCHEMA)

DEPENDENCIES = ['homeworks']

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


class HomeworksLight(HomeworksDevice, Light):
    """Homeworks Light."""

    def __init__(self, controller, addr, name, rate):
        """Create device with Addr, name, and rate."""
        super().__init__(controller, addr, name)
        self._rate = rate
        self._level = 0

    async def async_added_to_hass(self):
        """Called when entity is added to hass."""
        signal = ENTITY_SIGNAL.format(self._addr)
        _LOGGER.debug('connecting %s', signal)
        async_dispatcher_connect(
            self.hass, signal, self._update_callback)
        self._controller.request_dimmer_level(self._addr)

    @property
    def supported_features(self):
        """Supported features."""
        return SUPPORT_BRIGHTNESS

    def turn_on(self, **kwargs):
        """Turn on the light."""
        if ATTR_BRIGHTNESS in kwargs:
            self._set_brightness(kwargs[ATTR_BRIGHTNESS])
        else:
            self._set_brightness(255)

    def turn_off(self, **kwargs):
        """Turn off the light."""
        self._set_brightness(0)

    @property
    def brightness(self):
        """Control the brightness."""
        return self._level

    def _set_brightness(self, level):
        """Send the brightness level to the device."""
        self._controller.fade_dim(
            float((level*100.)/255.), self._rate,
            0, self._addr)

    @property
    def device_state_attributes(self):
        """Supported attributes."""
        return {'HomeworksAddress': self._addr}

    @property
    def is_on(self):
        """Is the light on/off."""
        return self._level != 0

    @callback
    def _update_callback(self, data):
        """Process device specific messages."""
        from pyhomeworks.pyhomeworks import HW_LIGHT_CHANGED

        _LOGGER.debug('_update_callback %s', data)
        msg_type, values = data
        if msg_type == HW_LIGHT_CHANGED:
            self._level = int((values[1] * 255.)/100.)
            self.async_schedule_update_ha_state(True)
