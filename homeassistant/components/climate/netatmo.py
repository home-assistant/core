"""
Support for Netatmo Smart Thermostat.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.netatmo/
"""
import logging
from datetime import timedelta
import voluptuous as vol

from homeassistant.const import TEMP_CELSIUS, ATTR_TEMPERATURE
from homeassistant.components.climate import (
    STATE_HEAT, STATE_IDLE, ClimateDevice, PLATFORM_SCHEMA)
from homeassistant.util import Throttle
from homeassistant.loader import get_component
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['netatmo']

_LOGGER = logging.getLogger(__name__)

CONF_RELAY = 'relay'
CONF_THERMOSTAT = 'thermostat'

DEFAULT_AWAY_TEMPERATURE = 14
# # The default offeset is 2 hours (when you use the thermostat itself)
DEFAULT_TIME_OFFSET = 7200
# # Return cached results if last scan was less then this time ago
# # NetAtmo Data is uploaded to server every hour
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=300)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_RELAY): cv.string,
    vol.Optional(CONF_THERMOSTAT, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
})


def setup_platform(hass, config, add_callback_devices, discovery_info=None):
    """Set up the NetAtmo Thermostat."""
    netatmo = get_component('netatmo')
    device = config.get(CONF_RELAY)

    import lnetatmo
    try:
        data = ThermostatData(netatmo.NETATMO_AUTH, device)
        for module_name in data.get_module_names():
            if CONF_THERMOSTAT in config:
                if config[CONF_THERMOSTAT] != [] and \
                   module_name not in config[CONF_THERMOSTAT]:
                    continue
            add_callback_devices([NetatmoThermostat(data, module_name)])
    except lnetatmo.NoDevice:
        return None


class NetatmoThermostat(ClimateDevice):
    """Representation a Netatmo thermostat."""

    def __init__(self, data, module_name, away_temp=None):
        """Initialize the sensor."""
        self._data = data
        self._state = None
        self._name = module_name
        self._target_temperature = None
        self._away = None
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._target_temperature

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._data.current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def current_operation(self):
        """Return the current state of the thermostat."""
        state = self._data.thermostatdata.relay_cmd
        if state == 0:
            return STATE_IDLE
        elif state == 100:
            return STATE_HEAT

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return self._away

    def turn_away_mode_on(self):
        """Turn away on."""
        mode = "away"
        temp = None
        self._data.thermostatdata.setthermpoint(mode, temp, endTimeOffset=None)
        self._away = True

    def turn_away_mode_off(self):
        """Turn away off."""
        mode = "program"
        temp = None
        self._data.thermostatdata.setthermpoint(mode, temp, endTimeOffset=None)
        self._away = False

    def set_temperature(self, endTimeOffset=DEFAULT_TIME_OFFSET, **kwargs):
        """Set new target temperature for 2 hours."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        mode = "manual"
        self._data.thermostatdata.setthermpoint(
            mode, temperature, endTimeOffset)
        self._target_temperature = temperature
        self._away = False

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from NetAtmo API and updates the states."""
        self._data.update()
        self._target_temperature = self._data.thermostatdata.setpoint_temp
        self._away = self._data.setpoint_mode == 'away'


class ThermostatData(object):
    """Get the latest data from Netatmo."""

    def __init__(self, auth, device=None):
        """Initialize the data object."""
        self.auth = auth
        self.thermostatdata = None
        self.module_names = []
        self.device = device
        self.current_temperature = None
        self.target_temperature = None
        self.setpoint_mode = None

    def get_module_names(self):
        """Return all module available on the API as a list."""
        self.update()
        if not self.device:
            for device in self.thermostatdata.modules:
                for module in self.thermostatdata.modules[device].values():
                    self.module_names.append(module['module_name'])
        else:
            for module in self.thermostatdata.modules[self.device].values():
                self.module_names.append(module['module_name'])
        return self.module_names

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Call the NetAtmo API to update the data."""
        import lnetatmo
        self.thermostatdata = lnetatmo.ThermostatData(self.auth)
        self.target_temperature = self.thermostatdata.setpoint_temp
        self.setpoint_mode = self.thermostatdata.setpoint_mode
        self.current_temperature = self.thermostatdata.temp
