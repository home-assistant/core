"""
Platform for Stiebel Eltron heat pumps with ISGWeb Modbus module.

Example configuration:

climate:
  - platform: stiebel_eltron
    name: LWZ504e
    host: 192.168.1.20
    port: 502

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/climate.stiebeleltron/
"""
import logging
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_NAME, CONF_SLAVE, TEMP_CELSIUS,
    ATTR_TEMPERATURE, DEVICE_DEFAULT_NAME)
from homeassistant.components.climate import (
    ClimateDevice, PLATFORM_SCHEMA, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_FAN_MODE, SUPPORT_OPERATION_MODE,
    STATE_AUTO, STATE_MANUAL, STATE_IDLE)
from homeassistant.components import modbus
import homeassistant.helpers.config_validation as cv


# REQUIREMENTS = ['pyflexit==0.3']
REQUIREMENTS = ['pymodbus==1.3.1']
# DEPENDENCIES = ['modbus']

STATE_DAYMODE = 'Tagbetrieb'
STATE_SETBACK = 'Absenkbetrieb'
STATE_DHW = 'Warmwasserbetrieb'
STATE_EMERGENCY = 'Notbetrieb'
STE_TO_HASS_STATE = {'AUTOMATIC': STATE_AUTO, 'MANUAL MODE': STATE_MANUAL,
                     'STANDBY': STATE_IDLE, 'DAY MODE': STATE_DAYMODE,
                     'SETBACK MODE': STATE_SETBACK, 'DHW': STATE_DHW,
                     'EMERGENCY OPERATION': STATE_EMERGENCY}

HASS_TO_STE_STATE = {STATE_AUTO: 'AUTOMATIC', STATE_MANUAL: 'MANUAL MODE',
                     STATE_IDLE: 'STANDBY', STATE_DAYMODE: 'DAY MODE',
                     STATE_SETBACK: 'SETBACK MODE', STATE_DHW: 'DHW',
                     STATE_EMERGENCY: 'EMERGENCY OPERATION'}

DEVICE_DEFAULT_NAME = "Stiebel Eltron Heatpump"
DEFAULT_PORT = 502
DEFAULT_UNIT = 1

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_SLAVE, default=DEFAULT_UNIT): vol.All(int, vol.Range(min=0, max=32)),
    vol.Optional(CONF_NAME, default=DEVICE_DEFAULT_NAME): cv.string
})

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE
# | SUPPORT_FAN_MODE


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the StiebelEltron Platform."""
    host = config.get(CONF_HOST, None)
    port = config.get(CONF_PORT, None)
    modbus_slave = config.get(CONF_SLAVE, None)
    name = config.get(CONF_NAME, None)

    from pymodbus.client.sync import ModbusTcpClient as ModbusClient
    client = ModbusClient(host=host, port=port)
    client.connect()
    add_devices([StiebelEltron(client, modbus_slave, name)], True)

    return True


class StiebelEltron(ClimateDevice):
    """Representation of a Stiebel Eltron heat pump."""

    def __init__(self, client, modbus_slave, name):
        """Initialize the unit."""
        from pystiebeleltron import pystiebeleltron
        self._name = name
        self._client = client
        self._slave = modbus_slave
        self._target_temperature = None
        self._current_temperature = None
        # self._current_fan_mode = None
        self._operation_modes = [STATE_AUTO, STATE_MANUAL, STATE_IDLE,
                                 STATE_DAYMODE, STATE_SETBACK, STATE_DHW,
                                 STATE_EMERGENCY]
        self._current_operation = None
        # self._fan_list = ['Off', 'Low', 'Medium', 'High']
        # self._current_operation = None
        # self._filter_hours = None
        self._filter_alarm = None
        # self._heat_recovery = None
        # self._heater_enabled = False
        # self._heating = None
        # self._cooling = None
        # self._alarm = False
        # self.unit = pyflexit.pyflexit(modbus.HUB, modbus_slave)
        self.unit = pystiebeleltron.pystiebeleltron(self._client, self._slave)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    def update(self):
        """Update unit attributes."""
        if not self.unit.update():
            _LOGGER.warning("Modbus read failed")

        self._target_temperature = self.unit.get_target_temp
        self._current_temperature = self.unit.get_current_temp
        # self._current_fan_mode =\
        #    self._fan_list[self.unit.get_fan_speed]
        # self._filter_hours = self.unit.get_filter_hours
        # Mechanical heat recovery, 0-100%
        # self._heat_recovery = self.unit.get_heat_recovery
        # Heater active 0-100%
        # self._heating = self.unit.get_heating
        # Cooling active 0-100%
        # self._cooling = self.unit.get_cooling
        # Filter alarm 0/1
        self._filter_alarm = self.unit.get_filter_alarm
        # Heater enabled or not. Does not mean it's necessarily heating
        # self._heater_enabled = self.unit.get_heater_enabled
        # Current operation mode
        self._current_operation = self.unit.get_operation

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {
            # 'filter_hours':     self._filter_hours,
            'filter_alarm':     self._filter_alarm,
            # 'heat_recovery':    self._heat_recovery,
            # 'heating':          self._heating,
            # 'heater_enabled':   self._heater_enabled,
            # 'cooling':          self._cooling
        }

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def operation_list(self):
        """List of the operation modes."""
        return self._operation_modes

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return STE_TO_HASS_STATE.get(self._current_operation)

    def set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        new_mode = HASS_TO_STE_STATE.get(operation_mode)
        self.unit.set_operation(new_mode)

#    @property
#    def current_fan_mode(self):
#        """Return the fan setting."""
#        return self._current_fan_mode

#    @property
#    def fan_list(self):
#        """Return the list of available fan modes."""
#        return self._fan_list

#    def set_temperature(self, **kwargs):
#        """Set new target temperature."""
#        if kwargs.get(ATTR_TEMPERATURE) is not None:
#            self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
#        self.unit.set_temp(self._target_temperature)

#    def set_fan_mode(self, fan_mode):
#        """Set new fan mode."""
#        self.unit.set_fan_speed(self._fan_list.index(fan_mode))
