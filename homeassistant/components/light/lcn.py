"""
Support for LCN lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.lcn/
"""

import logging

import voluptuous as vol

from homeassistant.components.lcn import LcnDevice
from homeassistant.components.lcn.core import (
    CONF_DIMMABLE, CONF_OUTPUT, CONF_TRANSITION, OUTPUT_PORTS,
    is_address)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_TRANSITION, PLATFORM_SCHEMA, SUPPORT_BRIGHTNESS,
    SUPPORT_TRANSITION, Light)
from homeassistant.const import CONF_ADDRESS, CONF_NAME
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['lcn']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_ADDRESS): is_address,
    vol.Required(CONF_OUTPUT): vol.Any(*(OUTPUT_PORTS)),
    vol.Optional(CONF_DIMMABLE, default=False): vol.Coerce(bool),
    vol.Optional(CONF_TRANSITION, default=0):
        vol.All(vol.Coerce(float), vol.Range(min=0., max=486.)),
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the LCN light platform."""
    device = LcnOutputLight(hass, config)
    async_add_entities([device])
    return True


class LcnOutputLight(LcnDevice, Light):
    """Representation of a LCN light for output ports."""

    def __init__(self, hass, config):
        """Initialize the LCN light."""
        LcnDevice.__init__(self, hass, config)

        self.output = self.pypck.lcn_defs.OutputPort[
            config[CONF_OUTPUT].upper()]

        self._transition = self.pypck.lcn_defs.time_to_ramp_value(
            config[CONF_TRANSITION] * 1000)
        self.dimmable = config[CONF_DIMMABLE]

        self._brightness = 255
        self._is_on = None

        self.hass.async_create_task(
            self.address_connection.activate_status_request_handler(
                self.output))

    @property
    def supported_features(self):
        """Flag supported features."""
        features = SUPPORT_TRANSITION
        if self.dimmable:
            features |= SUPPORT_BRIGHTNESS
        return features

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def is_on(self):
        """Return True if entity is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self._is_on = True
        if ATTR_BRIGHTNESS in kwargs:
            percent = int(kwargs[ATTR_BRIGHTNESS] / 255. * 100)
        else:
            percent = 100
        if ATTR_TRANSITION in kwargs:
            transition = self.pypck.lcn_defs.time_to_ramp_value(
                kwargs[ATTR_TRANSITION] * 1000)
        else:
            transition = self._transition

        self.address_connection.dim_output(self.output.value, percent,
                                           transition)
        await self.async_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self._is_on = False
        if ATTR_TRANSITION in kwargs:
            transition = self.pypck.lcn_defs.time_to_ramp_value(
                kwargs[ATTR_TRANSITION] * 1000)
        else:
            transition = self._transition

        self.address_connection.dim_output(self.output.value, 0, transition)
        await self.async_update_ha_state()

    def input_received(self, input_obj):
        """Set light state when LCN input object (command) is received."""
        if isinstance(input_obj, self.pypck.input.ModStatusOutput):
            if input_obj.get_output_id() == self.output.value:
                self._brightness = int(input_obj.get_percent() / 100.*255)
                self.async_schedule_update_ha_state()
