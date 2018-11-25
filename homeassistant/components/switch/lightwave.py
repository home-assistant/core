"""
Implements LightwaveRF switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.lightwave/
"""
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.const import CONF_DEVICES, CONF_NAME
from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.components.lightwave import LIGHTWAVE_LINK

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA}
})

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['lightwave']


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Find and return LightWave switches."""
    switches = []
    lwlink = hass.data[LIGHTWAVE_LINK]

    for device_id, device_config in config.get(CONF_DEVICES, {}).items():
        name = device_config[CONF_NAME]
        switches.append(LRFSwitch(name, device_id, lwlink))

    async_add_entities(switches)


class LRFSwitch(SwitchDevice):
    """Representation of a LightWaveRF switch."""

    def __init__(self, name, device_id, lwlink):
        """Initialize LRFSwitch entity."""
        self._name = name
        self._device_id = device_id
        self._state = None
        self._lwlink = lwlink

    @property
    def should_poll(self):
        """No polling needed for a LightWave light."""
        return False

    @property
    def name(self):
        """Lightwave switch name."""
        return self._name

    @property
    def is_on(self):
        """Lightwave switch is on state."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the LightWave switch on."""
        self._state = True
        self._lwlink.turn_on_switch(self._device_id, self._name)
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the LightWave switch off."""
        self._state = False
        self._lwlink.turn_off(self._device_id, self._name)
        self.async_schedule_update_ha_state()
