"""
Support for LCN sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.lcn/
"""

import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_FRIENDLY_NAME, CONF_NAME, CONF_UNIT_OF_MEASUREMENT)
import homeassistant.helpers.config_validation as cv

from ..lcn import LcnDevice
from ..lcn.core import (
    CONF_ADDRESS, CONF_SOURCE, KEYS, LED_PORTS, LOGICOP_PORTS, S0_INPUTS,
    SETPOINTS, THRESHOLDS, VAR_UNITS, VARIABLES, is_address)

DEPENDENCIES = ['lcn']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_ADDRESS): is_address,
    vol.Required(CONF_SOURCE): vol.Any(*(VARIABLES + SETPOINTS + THRESHOLDS +
                                         S0_INPUTS + LED_PORTS +
                                         LOGICOP_PORTS + KEYS)),
    vol.Optional(CONF_UNIT_OF_MEASUREMENT, default='native'):
        vol.Any(*VAR_UNITS),
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the LCN switch platform."""
    device_id = config[CONF_NAME]
    if CONF_FRIENDLY_NAME not in config:
        config[CONF_FRIENDLY_NAME] = device_id

    source = config[CONF_SOURCE]

    if source in VARIABLES + SETPOINTS + THRESHOLDS + S0_INPUTS:
        device = LcnVariableSensor(hass, config)
    elif (source in LED_PORTS) or (source in LOGICOP_PORTS):
        device = LcnLedLogicSensor(hass, config)
    else:
        device = LcnLockKeysSensor(hass, config)

    async_add_entities([device])
    return True


class LcnVariableSensor(LcnDevice):
    """Representation of a LCN sensor for variables."""

    def __init__(self, hass, config):
        """Initialize the LCN sensor."""
        LcnDevice.__init__(self, hass, config)

        self.variable = self.pypck.lcn_defs.Var[config[CONF_SOURCE].upper()]
        self.unit = self.pypck.lcn_defs.VarUnit[
            config[CONF_UNIT_OF_MEASUREMENT].upper()]

        self._value = None

        self.hass.async_create_task(
            self.module_connection.activate_status_request_handler(
                self.variable))

    @property
    def state(self):
        """Return the state of the entity."""
        return self._value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self.unit.value

    def module_input_received(self, input_obj):
        """Set sensor value when LCN input object (command) is received."""
        if isinstance(input_obj, self.pypck.input.ModStatusVar):
            if input_obj.get_var() == self.variable:
                self._value = (input_obj.get_value().to_var_unit(self.unit))

                self.async_schedule_update_ha_state()


class LcnLedLogicSensor(LcnDevice):
    """Representation of a LCN sensor for leds and logicops."""

    def __init__(self, hass, config):
        """Initialize the LCN sensor."""
        LcnDevice.__init__(self, hass, config)

        source = config[CONF_SOURCE]

        if source in LED_PORTS:
            self.source = self.pypck.lcn_defs.LedPort[source.upper()]
        else:
            self.source = self.pypck.lcn_defs.LogicOpPort[source.upper()]

        self._value = None

        self.hass.async_create_task(
            self.module_connection.activate_status_request_handler(
                self.source))

    @property
    def state(self):
        """Return the state of the entity."""
        return self._value

    def module_input_received(self, input_obj):
        """Set sensor value when LCN input object (command) is received."""
        if isinstance(input_obj, self.pypck.input.ModStatusLedsAndLogicOps):
            if self.source in self.pypck.lcn_defs.LedPort:
                self._value = input_obj.get_led_state(
                    self.source.value).name.lower()
            elif self.source in self.pypck.lcn_defs.LogicOpPort:
                self._value = input_obj.get_logic_op_state(
                    self.source.value).name.lower()

            self.async_schedule_update_ha_state()


class LcnLockKeysSensor(LcnDevice):
    """Representation of a LCN sensor for key locks."""

    def __init__(self, hass, config):
        """Initialize the LCN sensor."""
        LcnDevice.__init__(self, hass, config)

        self.source = self.pypck.lcn_defs.Key[config[CONF_SOURCE].upper()]
        self._value = None

        self.hass.async_create_task(
            self.module_connection.activate_status_request_handler(
                self.source))

    @property
    def state(self):
        """Return the state of the entity."""
        return self._value

    def module_input_received(self, input_obj):
        """Set sensor value when LCN input object (command) is received."""
        if isinstance(input_obj, self.pypck.input.ModStatusKeyLocks):
            if self.source in self.pypck.lcn_defs.Key:
                table_id = ord(self.source.name[0]) - 65
                key_id = int(self.source.name[1]) - 1

                self._value = input_obj.get_state(table_id, key_id)

            self.async_schedule_update_ha_state()
