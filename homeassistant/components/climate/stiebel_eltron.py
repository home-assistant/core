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
    SUPPORT_FAN_MODE)
from homeassistant.components import modbus
import homeassistant.helpers.config_validation as cv


# REQUIREMENTS = ['pyflexit==0.3']
REQUIREMENTS = ['pymodbus==1.3.1']
# DEPENDENCIES = ['modbus']

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

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE 
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
        # from pyflexit import pyflexit
        self._name = name
        self._client = client
        self._slave = modbus_slave
        self._target_temperature = None
        self._current_temperature = None
        # self._current_fan_mode = None
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
        self.unit = pystiebeleltron(self._client, self._slave)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    def update(self):
        """Update unit attributes."""
        if not self.unit.update():
            _LOGGER.warning("Modbus read failed")

        #self._client.connect()
        #rir1 = self._client.read_input_registers(0, 33, unit=self._slave)
        #rwhr = self._client.read_holding_registers(1001, 26, unit=self._slave)
        rir2 = self._client.read_input_registers(2000, 3, unit=self._slave)
        #rir3 = self._client.read_input_registers(3001, 31, unit=self._slave)
        #self._client.close()

        self._target_temperature = self.unit.get_target_temp
        self._current_temperature = self.unit.get_temp
        #self._current_fan_mode =\
        #    self._fan_list[self.unit.get_fan_speed]
        #self._filter_hours = self.unit.get_filter_hours
        # Mechanical heat recovery, 0-100%
        #self._heat_recovery = self.unit.get_heat_recovery
        # Heater active 0-100%
        #self._heating = self.unit.get_heating
        # Cooling active 0-100%
        #self._cooling = self.unit.get_cooling
        # Filter alarm 0/1
        #self._filter_alarm = self.unit.get_filter_alarm
        self._filter_alarm = bool(rir2.registers[0] & 0b011000100000000)
        # Heater enabled or not. Does not mean it's necessarily heating
        #self._heater_enabled = self.unit.get_heater_enabled
        # Current operation mode
        self._current_operation = self.unit.get_operation

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {
#            'filter_hours':     self._filter_hours,
            'filter_alarm':     self._filter_alarm,
#            'heat_recovery':    self._heat_recovery,
#            'heating':          self._heating,
#            'heater_enabled':   self._heater_enabled,
#            'cooling':          self._cooling
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
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self._current_operation

 #   @property
 #   def current_fan_mode(self):
 #       """Return the fan setting."""
 #       return self._current_fan_mode

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


# https://www.stiebel-eltron.de/content/dam/ste/de/de/home/services/Downloadlisten/ISG%20Modbus_Stiebel_Bedienungsanleitung.pdf

# Block 1 System values (Read input register) - page 29
#   Object designation                  Modbus address
BLOCK_1_START_ADDR = 0
BLOCK_1_REGMAP_INPUT = {
    'ACTUAL ROOM T HC1':                {'addr':  0, 'type': 2, 'value': 0},
    'SET ROOM TEMPERATURE HC1':         {'addr':  1, 'type': 2, 'value': 0},
    'RELATIVE HUMIDITY HC1':            {'addr':  2, 'type': 2, 'value': 0},
    'ACTUAL ROOM T HC2':                {'addr':  3, 'type': 2, 'value': 0},
    'SET ROOM TEMPERATURE HC2':         {'addr':  4, 'type': 2, 'value': 0},
    'RELATIVE HUMIDITY HC2':            {'addr':  5, 'type': 2, 'value': 0},
    'OUTSIDE TEMPERATURE':              {'addr':  6, 'type': 2, 'value': 0},
    'ACTUAL VALUE HC1':                 {'addr':  7, 'type': 2, 'value': 0},
    'SET VALUE HC1':                    {'addr':  8, 'type': 2, 'value': 0},
    'ACTUAL VALUE HC2':                 {'addr':  9, 'type': 2, 'value': 0},
    'SET VALUE HC2':                    {'addr': 10, 'type': 2, 'value': 0},
    'FLOW TEMPERATURE':                 {'addr': 11, 'type': 2, 'value': 0},
    'RETURN TEMPERATURE':               {'addr': 12, 'type': 2, 'value': 0},
    'PRESSURE HTG CIRC':                {'addr': 13, 'type': 2, 'value': 0},
    'FLOW R ATE':                       {'addr': 14, 'type': 2, 'value': 0},
    'ACTUAL DHW T':                     {'addr': 15, 'type': 2, 'value': 0},
    'DHW SET TEMPERATURE':              {'addr': 16, 'type': 2, 'value': 0},
    'VENTILATION AIR ACTUAL FAN SPEED': {'addr': 17, 'type': 6, 'value': 0},
    'VENTILATION AIR SET FLOW RATE':    {'addr': 18, 'type': 6, 'value': 0},
    'EXTRACT AIR ACTUAL FAN SPEED':     {'addr': 19, 'type': 6, 'value': 0},
    'EXTRACT AIR SET FLOW RATE':        {'addr': 20, 'type': 6, 'value': 0},
    'EXTRACT AIR HUMIDITY':             {'addr': 21, 'type': 6, 'value': 0},
    'EXTRACT AIR TEMP.':                {'addr': 22, 'type': 2, 'value': 0},
    'EXTRACT AIR DEW POINT':            {'addr': 23, 'type': 2, 'value': 0},
    'DEW POINT TEMP. HC1':              {'addr': 24, 'type': 2, 'value': 0},
    'DEW POINT TEMP. HC2':              {'addr': 25, 'type': 2, 'value': 0},
    'COLLECTOR TEMPERATURE':            {'addr': 26, 'type': 2, 'value': 0},
    'HOT GAS TEMPERATURE':              {'addr': 27, 'type': 2, 'value': 0},
    'HIGH PRESSURE':                    {'addr': 28, 'type': 7, 'value': 0},
    'LOW PRESSURE':                     {'addr': 29, 'type': 7, 'value': 0},
    'COMPRESSOR STARTS':                {'addr': 30, 'type': 6, 'value': 0},
    'COMPRESSOR SPEED':                 {'addr': 31, 'type': 2, 'value': 0},
    'MIXED WATER AMOUNT':               {'addr': 32, 'type': 6, 'value': 0}
}

# Block 2 System parameters (Read/write holding register) - page 30
BLOCK_2_START_ADDR = 1000

BLOCK_2_OPERATING_MODE = {
    # AUTOMATIK
    11: 'AUTOMATIC',
    # BEREITSCHAFT
    1: 'STANDBY',
    # TAGBETRIEB
    3: 'DAY MODE',
    # ABSENKBETRIEB
    4: 'SETBACK MODE',
    # WARMWASSER
    5: 'DHW',
    # HANDBETRIEB
    14: 'MANUAL MODE',
    # NOTBETRIEB
    0: 'EMERGENCY OPERATION'
}

BLOCK_2_RESET = {
    'OFF': {'value': 0},
    'ON':  {'value': 1}
}

BLOCK_2_RESTART_ISG = {
    'OFF':   {'value': 0},
    'RESET': {'value': 1},
    'MENU':  {'value': 2}
}

BLOCK_2_REGMAP_HOLDING = {
    'OPERATING MODE':           {'addr': 1000, 'type': 8, 'value': 0},
    'ROOM TEMP. DAY HC1':       {'addr': 1001, 'type': 2, 'value': 0},
    'ROOM TEMP. NIGHT HC1':     {'addr': 1002, 'type': 2, 'value': 0},
    'MANUAL SET HC1':           {'addr': 1003, 'type': 2, 'value': 0},
    'ROOM TEMP. DAY HC2 ':      {'addr': 1004, 'type': 2, 'value': 0},
    'ROOM TEMP. NIGHT HC2':     {'addr': 1005, 'type': 2, 'value': 0},
    'MANUAL SET HC2':           {'addr': 1006, 'type': 2, 'value': 0},
    'GRADIENT HC1':             {'addr': 1007, 'type': 7, 'value': 0},
    'LOW END HC1':              {'addr': 1008, 'type': 2, 'value': 0},
    'GRADIENT HC2':             {'addr': 1009, 'type': 7, 'value': 0},
    'LOW END HC2':              {'addr': 1010, 'type': 2, 'value': 0},
    'DHW SET DAY':              {'addr': 1011, 'type': 2, 'value': 0},
    'DHW SET NIGHT':            {'addr': 1012, 'type': 2, 'value': 0},
    'DHW SET MANUAL':           {'addr': 1013, 'type': 2, 'value': 0},
    'MWM SET DAY':              {'addr': 1014, 'type': 6, 'value': 0},
    'MWM SET NIGHT':            {'addr': 1015, 'type': 6, 'value': 0},
    'MWM SET MANUAL':           {'addr': 1016, 'type': 6, 'value': 0},
    'DAY STAGE':                {'addr': 1017, 'type': 6, 'value': 0},
    'NIGHT STAGE':              {'addr': 1018, 'type': 6, 'value': 0},
    'PARTY STAGE':              {'addr': 1019, 'type': 6, 'value': 0},
    'MANUAL STAGE':             {'addr': 1020, 'type': 6, 'value': 0},
    'ROOM TEMP. C. DAY HC1':    {'addr': 1021, 'type': 2, 'value': 0},
    'ROOM TEMP. C. NIGHT HC1':  {'addr': 1022, 'type': 2, 'value': 0},
    'ROOM TEMP. c. DAY HC2':    {'addr': 1023, 'type': 2, 'value': 0},
    'ROOM TEMP. c. NIGHT HC2':  {'addr': 1024, 'type': 2, 'value': 0},
    'RESET':                    {'addr': 1025, 'type': 6, 'value': 0},
    'RESTART ISG':              {'addr': 1026, 'type': 6, 'value': 0}
}


class pystiebeleltron(object):
    def __init__(self, conn, slave, update_on_read=False):
        self._conn = conn
        self._block_1_input_regs = BLOCK_1_REGMAP_INPUT
        self._block_2_holding_regs = BLOCK_2_REGMAP_HOLDING
        self._slave = slave
        self._target_temp = None
        self._current_temp = None
        self._current_fan = None
        self._current_operation = None
        self._filter_hours = None
        self._filter_alarm = None
        self._heat_recovery = None
        self._heater_enabled = False
        self._heating = None
        self._cooling = None
        self._alarm = False
        self._update_on_read = update_on_read

    def update(self):
        ret = True
        try:
            block_1_result_input = self._conn.read_input_registers(
                unit=self._slave,
                address=BLOCK_1_START_ADDR,
                count=len(self._block_1_input_regs)).registers
            block_2_result_holding = self._conn.read_holding_registers(
                unit=self._slave,
                address=BLOCK_2_START_ADDR,
                count=len(self._block_2_holding_regs)).registers
        except AttributeError:
            # The unit does not reply reliably
            ret = False
            print("Modbus read failed")
        else:
            for k in self._block_1_input_regs:
                self._block_1_input_regs[k]['value'] = \
                    block_1_result_input[self._block_1_input_regs[k]['addr'] - BLOCK_1_START_ADDR]
            for k in self._block_2_holding_regs:
                self._block_2_holding_regs[k]['value'] = \
                    block_2_result_holding[self._block_2_holding_regs[k]['addr'] - BLOCK_2_START_ADDR]

        self._target_temp = \
            (self._block_1_input_regs['SET ROOM TEMPERATURE HC1']['value'] * 0.1)
        # Temperature directly after heat recovery and heater
        self._current_temp = \
            (self._block_1_input_regs['ACTUAL ROOM T HC1']['value'] * 0.1)
        #self._current_fan = \
        #    (self._input_regs['ActualSetAirSpeed']['value'])
        # Hours since last filter reset
        #self._filter_hours = \
        #    self._input_regs['FilterTimer']['value']
        # Mechanical heat recovery, 0-100%
        #self._heat_recovery = \
        #    self._input_regs['HeatExchanger']['value']
        # Heater active 0-100%
        #self._heating = \
        #    self._input_regs['Heating']['value']
        # Cooling active 0-100%
        #self._cooling = \
        #    self._input_regs['Cooling']['value']
        # Filter alarm 0/1
        #self._filter_alarm = \
        #    bool(self._input_regs['ReplaceFilterAlarm']['value'])
        # Heater enabled or not. Does not mean it's necessarily heating
        #self._heater_enabled = \
        #    bool(self._input_regs['HeatingBatteryActive']['value'])
        # Current operation mode
        op_mode = self._block_2_holding_regs['OPERATING MODE']['value']
        self._current_operation = BLOCK_2_OPERATING_MODE.get(op_mode, 'Unknown1')
        #if self._heating:
        #    self._current_operation = 'Heating'
        #elif self._cooling:
        #    self._current_operation = 'Cooling'
        #elif self._heat_recovery:
        #    self._current_operation = 'Recovering'
        #elif self._input_regs['ActualSetAirSpeed']['value']:
        #    self._current_operation = 'Fan Only'
        #else:
        #    self._current_operation = 'Off'

        return ret

    def get_raw_input_register(self, name):
        """Get raw register value by name."""
        if self._update_on_read:
            self.update()
        return self._block_1_input_regs[name]

    def get_raw_holding_register(self, name):
        """Get raw register value by name."""
        if self._update_on_read:
            self.update()
        return self._block_2_holding_regs[name]

    def set_raw_holding_register(self, name, value):
        """Write to register by name."""
        return
        #self._conn.write_register(
        #    unit=self._slave,
        #    address=(self._holding_regs[name]['addr']),
        #    value=value)

    def set_temp(self, temp):
        return
        #self._conn.write_register(
        #    unit=self._slave,
        #    address=(self._holding_regs['SetAirTemperature']['addr']),
        #    value=round(temp * 10.0))

    def set_fan_speed(self, fan):
        return
        #self._conn.write_register(
        #    unit=self._slave,
        #    address=(self._holding_regs['SetAirSpeed']['addr']),
        #    value=fan)

    @property
    def get_temp(self):
        """Get the current temperature."""
        if self._update_on_read:
            self.update()
        return self._current_temp

    @property
    def get_target_temp(self):
        """Get target temperature."""
        if self._update_on_read:
            self.update()
        return self._target_temp

    @property
    def get_filter_hours(self):
        """Get the number of hours since filter reset."""
        if self._update_on_read:
            self.update()
        return self._filter_hours

    @property
    def get_operation(self):
        """Return the current mode of operation."""
        if self._update_on_read:
            self.update()
        return self._current_operation

    @property
    def get_fan_speed(self):
        """Return the current fan speed (0-4)."""
        if self._update_on_read:
            self.update()
        return self._current_fan

    @property
    def get_heat_recovery(self):
        """Return current heat recovery percentage."""
        if self._update_on_read:
            self.update()
        return self._heat_recovery

    @property
    def get_heating(self):
        """Return heater percentage."""
        if self._update_on_read:
            self.update()
        return self._heating

    @property
    def get_heater_enabled(self):
        """Return heater enabled."""
        if self._update_on_read:
            self.update()
        return self._heater_enabled

    @property
    def get_cooling(self):
        """Cooling active percentage."""
        if self._update_on_read:
            self.update()
        return self._cooling

    @property
    def get_filter_alarm(self):
        """Change filter alarm."""
        if self._update_on_read:
            self.update()
        return self._filter_alarm
