"""
homeassistant.components.light.lightwave
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Implements LightwaveRF lights.


My understanding of the LightWave Hub is that devices cannot be discovered so must be
registered manually. This is done in the configuration file:

switch:
  - platform: lightwave
    devices:
      R1D2:
        name: Room one Device two
      R2D1:
        name: Room two Device one

Each device requires an id and a name. THe id takes the from R#D# where R# is the room number 
and D# is the device number.

If devices are missing the default is to generate 15 rooms with 8 lights. From this you will
be able to determine the room and device number for each light.

TODO: 
Add a registration button. Until then the following command needs to be sent to the LightwaveRF hub:
    echo -ne "100,\!F*p." | nc -u -w1 LW_HUB_IP_ADDRESS 9760

When this is sent you have 12 seconds to acknowledge the message on the hub.

For more details on the api see: https://api.lightwaverf.com/
"""

import asyncio
import logging
import voluptuous as vol
from homeassistant.const import CONF_DEVICES, CONF_NAME
from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA}
})

_LOGGER = logging.getLogger(__name__)

LIGHTWAVE_LINK = 'lightwave_link'
DEPENDENCIES = ['lightwave']


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """ Find and return LightWave lights """
    lights = []
    lwlink = hass.data[LIGHTWAVE_LINK]

    for device_id, device_config in config.get(CONF_DEVICES, {}).items():
        name = device_config[CONF_NAME]
        lights.append(LRFLight(name, device_id, lwlink))

    async_add_entities(lights)


class LRFLight(Light):
    """ Provides a LightWave light. """

    def __init__(self, name, device_id, lwlink):
        self._name = name
        self._device_id = device_id
        self._state = None
        self._brightness = 255
        self._lwlink = lwlink

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def should_poll(self):
        """ No polling needed for a LightWave light. """
        return False

    @property
    def name(self):
        """ Returns the name of the LightWave light. """
        return self._name

    @property
    def brightness(self):
        """ Brightness of this light between 0..255. """
        return self._brightness

    @property
    def is_on(self):
        """ True if the LightWave light is on. """
        return self._state

    async def async_turn_on(self, **kwargs):
        """ Turn the LightWave light on. """
        self._state = True

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        if not self._brightness == 255:
            self._lwlink.turn_on_with_brightness(
                self._device_id, self._name, self._brightness)
        else:
            self._lwlink.turn_on_light(self._device_id, self._name)

        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """ Turn the LightWave light off. """
        self._state = False
        self._lwlink.turn_off(self._device_id, self._name)
        self.async_schedule_update_ha_state()
