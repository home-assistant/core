"""Component for interfacing to Lutron Homeworks lights.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.homeworks/
"""
import logging

from homeassistant.components.homeworks import (
    HomeworksDevice, HOMEWORKS_CONTROLLER, ENTITY_SIGNAL,
    CONF_DIMMERS, CONF_ADDR, CONF_RATE)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect)

DEPENDENCIES = ['homeworks']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discover_info=None):
    """Set up Homeworks lights."""
    if discover_info is None:
        return

    controller = hass.data[HOMEWORKS_CONTROLLER]
    devs = []
    for dimmer in discover_info[CONF_DIMMERS]:
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
        self._prev_level = 0

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
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
            new_level = kwargs[ATTR_BRIGHTNESS]
        elif self._prev_level == 0:
            new_level = 255
        else:
            new_level = self._prev_level
        self._set_brightness(new_level)

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
        return {'homeworks_address': self._addr}

    @property
    def is_on(self):
        """Is the light on/off."""
        return self._level != 0

    @callback
    def _update_callback(self, msg_type, values):
        """Process device specific messages."""
        from pyhomeworks.pyhomeworks import HW_LIGHT_CHANGED

        if msg_type == HW_LIGHT_CHANGED:
            self._level = int((values[1] * 255.)/100.)
            if self._level != 0:
                self._prev_level = self._level
            self.async_schedule_update_ha_state()
