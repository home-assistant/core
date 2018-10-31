"""
Support for LCN covers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.lcn/
"""

import logging

import voluptuous as vol

from homeassistant.components.cover import PLATFORM_SCHEMA, CoverDevice
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_NAME
import homeassistant.helpers.config_validation as cv

from ..lcn import LcnDevice
from ..lcn.core import CONF_ADDRESS, CONF_MOTOR, MOTOR_PORTS, is_address

DEPENDENCIES = ['lcn']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_ADDRESS): is_address,
    vol.Required(CONF_MOTOR): vol.Any(*MOTOR_PORTS),
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    })


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Setups the LCN cover platform."""
    device_id = config[CONF_NAME]
    if CONF_FRIENDLY_NAME not in config:
        config[CONF_FRIENDLY_NAME] = device_id

    device = LcnCover(hass, config)

    async_add_entities([device])
    return True


class LcnCover(LcnDevice, CoverDevice):
    """Representation of a LCN cover."""

    def __init__(self, hass, config):
        """Initialize the LCN cover."""
        LcnDevice.__init__(self, hass, config)

        self.motor = self.pypck.lcn_defs.MotorPort[config[CONF_MOTOR].upper()]
        self.motor_port_onoff = self.motor.value * 2
        self.motor_port_updown = self.motor_port_onoff + 1

        self._closed = None

        self.hass.async_create_task(
            self.module_connection.activate_status_request_handler(self.motor))

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._closed

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        self._closed = False
        states = [self.pypck.lcn_defs.MotorStateModifier.NOCHANGE] * 4
        states[self.motor.value] = self.pypck.lcn_defs.MotorStateModifier.DOWN
        self.module_connection.control_motors(states)
        await self.async_update_ha_state()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        self._closed = True
        states = [self.pypck.lcn_defs.MotorStateModifier.NOCHANGE] * 4
        states[self.motor.value] = self.pypck.lcn_defs.MotorStateModifier.UP
        self.module_connection.control_motors(states)
        await self.async_update_ha_state()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        states = [self.pypck.lcn_defs.MotorStateModifier.NOCHANGE] * 4
        states[self.motor.value] = self.pypck.lcn_defs.MotorStateModifier.STOP
        self.module_connection.control_motors(states)
        await self.async_update_ha_state()

    def module_input_received(self, input_obj):
        """Set cover states when LCN input object (command) is received."""
        if isinstance(input_obj, self.pypck.input.ModStatusRelays):
            states = input_obj.states  # list of boolean values (relay on/off)
            if states[self.motor_port_onoff]:  # motor is on
                self._closed = states[self.motor_port_updown]  # set direction

            self.async_schedule_update_ha_state()
