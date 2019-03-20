"""
Support for eQ-3 Bluetooth Smart thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.eq3btsmart/
"""
import logging

import voluptuous as vol

from homeassistant.components.climate import ClimateDevice, PLATFORM_SCHEMA
from homeassistant.components.climate.const import (
    STATE_HEAT, STATE_MANUAL, STATE_ECO,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE, SUPPORT_AWAY_MODE,
    SUPPORT_ON_OFF)
from homeassistant.const import (
    ATTR_TEMPERATURE, CONF_MAC, CONF_DEVICES, STATE_ON, STATE_OFF,
    TEMP_CELSIUS, PRECISION_HALVES)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['python-eq3bt==0.1.9', 'construct==2.9.45']

_LOGGER = logging.getLogger(__name__)

STATE_BOOST = 'boost'

ATTR_STATE_WINDOW_OPEN = 'window_open'
ATTR_STATE_VALVE = 'valve'
ATTR_STATE_LOCKED = 'is_locked'
ATTR_STATE_LOW_BAT = 'low_battery'
ATTR_STATE_AWAY_END = 'away_end'

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_MAC): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICES):
        vol.Schema({cv.string: DEVICE_SCHEMA}),
})

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE |
                 SUPPORT_AWAY_MODE | SUPPORT_ON_OFF)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the eQ-3 BLE thermostats."""
    devices = []

    for name, device_cfg in config[CONF_DEVICES].items():
        mac = device_cfg[CONF_MAC]
        devices.append(EQ3BTSmartThermostat(mac, name))

    add_entities(devices)


class EQ3BTSmartThermostat(ClimateDevice):
    """Representation of an eQ-3 Bluetooth Smart thermostat."""

    def __init__(self, _mac, _name):
        """Initialize the thermostat."""
        # We want to avoid name clash with this module.
        import eq3bt as eq3  # pylint: disable=import-error

        self.modes = {
            eq3.Mode.Open: STATE_ON,
            eq3.Mode.Closed: STATE_OFF,
            eq3.Mode.Auto: STATE_HEAT,
            eq3.Mode.Manual: STATE_MANUAL,
            eq3.Mode.Boost: STATE_BOOST,
            eq3.Mode.Away: STATE_ECO,
        }

        self.reverse_modes = {v: k for k, v in self.modes.items()}

        self._name = _name
        self._thermostat = eq3.Thermostat(_mac)
        self._target_temperature = None
        self._target_mode = None

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def available(self) -> bool:
        """Return if thermostat is available."""
        return self.current_operation is not None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement that is used."""
        return TEMP_CELSIUS

    @property
    def precision(self):
        """Return eq3bt's precision 0.5."""
        return PRECISION_HALVES

    @property
    def current_temperature(self):
        """Can not report temperature, so return target_temperature."""
        return self.target_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._thermostat.target_temperature

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._target_temperature = temperature
        self._thermostat.target_temperature = temperature

    @property
    def current_operation(self):
        """Return the current operation mode."""
        if self._thermostat.mode < 0:
            return None
        return self.modes[self._thermostat.mode]

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return [x for x in self.modes.values()]

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        self._target_mode = operation_mode
        self._thermostat.mode = self.reverse_modes[operation_mode]

    def turn_away_mode_off(self):
        """Away mode off turns to AUTO mode."""
        self.set_operation_mode(STATE_HEAT)

    def turn_away_mode_on(self):
        """Set away mode on."""
        self.set_operation_mode(STATE_ECO)

    @property
    def is_away_mode_on(self):
        """Return if we are away."""
        return self.current_operation == STATE_ECO

    def turn_on(self):
        """Turn device on."""
        self.set_operation_mode(STATE_HEAT)

    def turn_off(self):
        """Turn device off."""
        self.set_operation_mode(STATE_OFF)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._thermostat.min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._thermostat.max_temp

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        dev_specific = {
            ATTR_STATE_AWAY_END: self._thermostat.away_end,
            ATTR_STATE_LOCKED: self._thermostat.locked,
            ATTR_STATE_LOW_BAT: self._thermostat.low_battery,
            ATTR_STATE_VALVE: self._thermostat.valve_state,
            ATTR_STATE_WINDOW_OPEN: self._thermostat.window_open,
        }

        return dev_specific

    def update(self):
        """Update the data from the thermostat."""
        # pylint: disable=import-error,no-name-in-module
        from bluepy.btle import BTLEException
        try:
            self._thermostat.update()
        except BTLEException as ex:
            _LOGGER.warning("Updating the state failed: %s", ex)

        if (self._target_temperature and
                self._thermostat.target_temperature
                != self._target_temperature):
            self.set_temperature(temperature=self._target_temperature)
        else:
            self._target_temperature = None
        if (self._target_mode and
                self.modes[self._thermostat.mode] != self._target_mode):
            self.set_operation_mode(operation_mode=self._target_mode)
        else:
            self._target_mode = None
