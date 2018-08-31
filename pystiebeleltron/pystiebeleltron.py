"""
Connection to a Stiebel Eltron ModBus API.

See API details:
https://www.stiebel-eltron.de/content/dam/ste/de/de/home/services/Downloadlisten/ISG%20Modbus_Stiebel_Bedienungsanleitung.pdf

Types of data:

Data | Value      | Multiplier  | Multiplier  | Signed | Step   | Step
type | range      | for reading | for writing |        | size 1 | size 5
-----|------------|-------------|-------------|--------|--------|-------
2    | -3276.8 to | 0.1         | 10          | Yes    | 0.1    | 0.5
     |  3276.7    |             |             |        |        |
6    | 0 to 65535 | 1           | 1           | No     | 1      | 5
7    | -327.68 to | 0.01        | 100         | Yes    | 0.01   | 0.05
     |  327.67    |             |             |        |        |
8    | 0 to 255   | 1           | 1           | No     | 1      | 5
"""

UNAVAILABLE_OBJECT = 32768

# Block 1 System values (Read input register) - page 29
#   Object designation                  Modbus address
B1_START_ADDR = 0

B1_REGMAP_INPUT = {
    'ACTUAL_ROOM_TEMPERATURE_HC1':      {'addr':  0, 'type': 2, 'value': 0},
    'SET_ROOM_TEMPERATURE_HC1':         {'addr':  1, 'type': 2, 'value': 0},
    'RELATIVE_HUMIDITY_HC1':            {'addr':  2, 'type': 2, 'value': 0},
    'ACTUAL_ROOM_TEMPERATURE_HC2':      {'addr':  3, 'type': 2, 'value': 0},
    'SET_ROOM_TEMPERATURE_HC2':         {'addr':  4, 'type': 2, 'value': 0},
    'RELATIVE_HUMIDITY_HC2':            {'addr':  5, 'type': 2, 'value': 0},
    'OUTSIDE_TEMPERATURE':              {'addr':  6, 'type': 2, 'value': 0},
    'ACTUAL_VALUE_HC1':                 {'addr':  7, 'type': 2, 'value': 0},
    'SET_VALUE_HC1':                    {'addr':  8, 'type': 2, 'value': 0},
    'ACTUAL_VALUE_HC2':                 {'addr':  9, 'type': 2, 'value': 0},
    'SET_VALUE_HC2':                    {'addr': 10, 'type': 2, 'value': 0},
    'FLOW_TEMPERATURE':                 {'addr': 11, 'type': 2, 'value': 0},
    'RETURN_TEMPERATURE':               {'addr': 12, 'type': 2, 'value': 0},
    'PRESSURE_HEATING_CIRCUIT':         {'addr': 13, 'type': 2, 'value': 0},
    'FLOW_RATE':                        {'addr': 14, 'type': 2, 'value': 0},
    'ACTUAL_DHW_TEMPERATURE':           {'addr': 15, 'type': 2, 'value': 0},
    'SET_DHW_TEMPERATURE':              {'addr': 16, 'type': 2, 'value': 0},
    'VENTILATION_AIR_ACTUAL_FAN_SPEED': {'addr': 17, 'type': 6, 'value': 0},
    'VENTILATION_AIR_SET_FLOW_RATE':    {'addr': 18, 'type': 6, 'value': 0},
    'EXTRACT_AIR_ACTUAL_FAN_SPEED':     {'addr': 19, 'type': 6, 'value': 0},
    'EXTRACT_AIR_SET_FLOW_RATE':        {'addr': 20, 'type': 6, 'value': 0},
    'EXTRACT_AIR_HUMIDITY':             {'addr': 21, 'type': 6, 'value': 0},
    'EXTRACT_AIR_TEMPERATURE':          {'addr': 22, 'type': 2, 'value': 0},
    'EXTRACT_AIR_DEW_POINT':            {'addr': 23, 'type': 2, 'value': 0},
    'DEW_POINT_TEMPERATUR_HC1':         {'addr': 24, 'type': 2, 'value': 0},
    'DEW_POINT_TEMPERATUR_HC2':         {'addr': 25, 'type': 2, 'value': 0},
    'COLLECTOR_TEMPERATURE':            {'addr': 26, 'type': 2, 'value': 0},
    'HOT_GAS_TEMPERATURE':              {'addr': 27, 'type': 2, 'value': 0},
    'HIGH_PRESSURE':                    {'addr': 28, 'type': 7, 'value': 0},
    'LOW_PRESSURE':                     {'addr': 29, 'type': 7, 'value': 0},
    'COMPRESSOR_STARTS':                {'addr': 30, 'type': 6, 'value': 0},
    'COMPRESSOR_SPEED':                 {'addr': 31, 'type': 2, 'value': 0},
    'MIXED_WATER_AMOUNT':               {'addr': 32, 'type': 6, 'value': 0}
}


# Block 2 System parameters (Read/write holding register) - page 30
B2_START_ADDR = 1000

B2_REGMAP_HOLDING = {
    'OPERATING_MODE':           {'addr': 1000, 'type': 8, 'value': 0},
    'ROOM_TEMP_HEAT_DAY_HC1':   {'addr': 1001, 'type': 2, 'value': 0},
    'ROOM_TEMP_HEAT_NIGHT_HC1': {'addr': 1002, 'type': 2, 'value': 0},
    'MANUAL_SET_TEMP_HC1':      {'addr': 1003, 'type': 2, 'value': 0},
    'ROOM_TEMP_HEAT_DAY_HC2':   {'addr': 1004, 'type': 2, 'value': 0},
    'ROOM_TEMP_HEAT_NIGHT_HC2': {'addr': 1005, 'type': 2, 'value': 0},
    'MANUAL_SET_TEAMP_HC2':     {'addr': 1006, 'type': 2, 'value': 0},
    'GRADIENT_HC1':             {'addr': 1007, 'type': 7, 'value': 0},
    'LOW_END_HC1':              {'addr': 1008, 'type': 2, 'value': 0},
    'GRADIENT_HC2':             {'addr': 1009, 'type': 7, 'value': 0},
    'LOW_END_HC2':              {'addr': 1010, 'type': 2, 'value': 0},
    'DHW_TEMP_SET_DAY':         {'addr': 1011, 'type': 2, 'value': 0},
    'DHW_TEMP_SET_NIGHT':       {'addr': 1012, 'type': 2, 'value': 0},
    'DHW_TEMP_SET_MANUAL':      {'addr': 1013, 'type': 2, 'value': 0},
    'MWM_SET_DAY':              {'addr': 1014, 'type': 6, 'value': 0},
    'MWM_SET_NIGHT':            {'addr': 1015, 'type': 6, 'value': 0},
    'MWM_SET_MANUAL':           {'addr': 1016, 'type': 6, 'value': 0},
    'DAY_STAGE':                {'addr': 1017, 'type': 6, 'value': 0},
    'NIGHT_STAGE':              {'addr': 1018, 'type': 6, 'value': 0},
    'PARTY_STAGE':              {'addr': 1019, 'type': 6, 'value': 0},
    'MANUAL_STAGE':             {'addr': 1020, 'type': 6, 'value': 0},
    'ROOM_TEMP_COOL_DAY_HC1':   {'addr': 1021, 'type': 2, 'value': 0},
    'ROOM_TEMP_COOL_NIGHT_HC1': {'addr': 1022, 'type': 2, 'value': 0},
    'ROOM_TEMP_COOL_DAY_HC2':   {'addr': 1023, 'type': 2, 'value': 0},
    'ROOM_TEMP_COOL_NIGHT_HC2': {'addr': 1024, 'type': 2, 'value': 0},
    'RESET':                    {'addr': 1025, 'type': 6, 'value': 0},
    'RESTART_ISG':              {'addr': 1026, 'type': 6, 'value': 0}
}

B2_OPERATING_MODE_READ = {
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

B2_OPERATING_MODE_WRITE = {
    'AUTOMATIC': 11,
    'STANDBY': 1,
    'DAY MODE': 3,
    'SETBACK MODE': 4,
    'DHW': 5,
    'MANUAL MODE': 14,
    'EMERGENCY OPERATION': 0
}

B2_RESET = {
    'OFF': 0,
    'ON': 1
}

B2_RESTART_ISG = {
    'OFF': 0,
    'RESET': 1,
    'MENU': 2
}

# Block 3 System status (Read input register) - page 31
B3_START_ADDR = 2000

B3_REGMAP_INPUT = {
    'OPERATING_STATUS': {'addr': 2000, 'type': 6, 'value': 0},
    'FAULT_STATUS':     {'addr': 2001, 'type': 6, 'value': 0},
    'BUS_STATUS':       {'addr': 2002, 'type': 6, 'value': 0}
}

B3_OPERATING_STATUS = {
    'SWITCHING PROGRAM ENABLED': 0,
    'COMPRESSOR': 1,
    'HEATING': 2,
    'COOLING': 3,
    'DHW': 4,
    'ELECTRIC REHEATING': 5,
    'SERVICE': 6,
    'POWER-OFF': 7,
    'FILTER': 8,
    'VENTILATION': 9,
    'HEATING CIRCUIT PUMP': 10,
    'EVAPORATOR DEFROST': 11,
    'FILTER EXTRACT AIR': 12,
    'FILTER VENTILATION AIR': 13,
    'HEAT-UP PROGRAM': 14
}

B3_FAULT_STATUS = {
    'NO_FAULT': 0,
    'FAULT': 1
}

B3_BUS_STATUS = {
    'STATUS OK': 0,
    'STATUS ERROR': -1,
    'ERROR-PASSIVE': -2,
    'BUS-OFF': -3,
    'PHYSICAL-ERROR': -4
}


class pystiebeleltron(object):
    """API object."""

    def __init__(self, conn, slave, update_on_read=False):
        """Initialize Stiebel Eltron communication."""
        self._conn = conn
        self._block_1_input_regs = B1_REGMAP_INPUT
        self._block_2_holding_regs = B2_REGMAP_HOLDING
        self._block_3_input_regs = B3_REGMAP_INPUT
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
        """Request current values from heat pump."""
        ret = True
        try:
            block_1_result_input = self._conn.read_input_registers(
                unit=self._slave,
                address=B1_START_ADDR,
                count=len(self._block_1_input_regs)).registers
            block_2_result_holding = self._conn.read_holding_registers(
                unit=self._slave,
                address=B2_START_ADDR,
                count=len(self._block_2_holding_regs)).registers
            block_3_result_input = self._conn.read_input_registers(
                unit=self._slave,
                address=B3_START_ADDR,
                count=len(self._block_3_input_regs)).registers
        except AttributeError:
            # The unit does not reply reliably
            ret = False
            print("Modbus read failed")
        else:
            for k in self._block_1_input_regs:
                self._block_1_input_regs[k]['value'] = \
                    block_1_result_input[self._block_1_input_regs[k]['addr'] - B1_START_ADDR]
            for k in self._block_2_holding_regs:
                self._block_2_holding_regs[k]['value'] = \
                    block_2_result_holding[self._block_2_holding_regs[k]['addr'] - B2_START_ADDR]
            for k in self._block_3_input_regs:
                self._block_3_input_regs[k]['value'] = \
                    block_3_result_input[self._block_3_input_regs[k]['addr'] - B3_START_ADDR]

        self._target_temp = \
            (self._block_1_input_regs['SET_ROOM_TEMPERATURE_HC1']['value']
                * 0.1)
        # Temperature directly after heat recovery and heater
        self._current_temp = \
            (self._block_1_input_regs['ACTUAL_ROOM_TEMPERATURE_HC1']['value']
                * 0.1)
        # self._current_fan = \
        #    (self._input_regs['ActualSetAirSpeed']['value'])
        # Hours since last filter reset
        # self._filter_hours = \
        #    self._input_regs['FilterTimer']['value']
        # Mechanical heat recovery, 0-100%
        # self._heat_recovery = \
        #    self._input_regs['HeatExchanger']['value']
        # Heater active 0-100%
        # self._heating = \
        #    self._input_regs['Heating']['value']
        # Cooling active 0-100%
        # self._cooling = \
        #    self._input_regs['Cooling']['value']
        # Filter alarm 0/1
        # self._filter_alarm = \
        #    bool(self._input_regs['ReplaceFilterAlarm']['value'])
        self._filter_alarm = \
            bool(self._block_3_input_regs['OPERATING_STATUS']['value'] & 0b011000100000000)
        # Heater enabled or not. Does not mean it's necessarily heating
        # self._heater_enabled = \
        #    bool(self._input_regs['HeatingBatteryActive']['value'])
        # Current operation mode
        self._current_operation = self._block_2_holding_regs['OPERATING_MODE']['value']
        # if self._heating:
        #    self._current_operation = 'Heating'
        # elif self._cooling:
        #    self._current_operation = 'Cooling'
        # elif self._heat_recovery:
        #    self._current_operation = 'Recovering'
        # elif self._input_regs['ActualSetAirSpeed']['value']:
        #    self._current_operation = 'Fan Only'
        # else:
        #    self._current_operation = 'Off'

        return ret

#    def get_raw_input_register(self, name):
#        """Get raw register value by name."""
#        if self._update_on_read:
#            self.update()
#        return self._block_1_input_regs[name]

#    def get_raw_holding_register(self, name):
#        """Get raw register value by name."""
#        if self._update_on_read:
#            self.update()
#        return self._block_2_holding_regs[name]

#    def set_raw_holding_register(self, name, value):
#        """Write to register by name."""
#        self._conn.write_register(
#            unit=self._slave,
#            address=(self._holding_regs[name]['addr']),
#            value=value)

#    def set_temp(self, temp):
#        self._conn.write_register(
#            unit=self._slave,
#            address=(self._holding_regs['SetAirTemperature']['addr']),
#            value=round(temp * 10.0))

#    def set_fan_speed(self, fan):
#        self._conn.write_register(
#            unit=self._slave,
#            address=(self._holding_regs['SetAirSpeed']['addr']),
#            value=fan)

    @property
    def get_current_temp(self):
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

#    @property
#    def get_filter_hours(self):
#        """Get the number of hours since filter reset."""
#        if self._update_on_read:
#            self.update()
#        return self._filter_hours

    @property
    def get_operation(self):
        """Return the current mode of operation."""
        if self._update_on_read:
            self.update()
        return B2_OPERATING_MODE_READ.get(self._current_operation,
                                          'UNKNOWN')

    def set_operation(self, mode):
        """Set the operation mode."""
        self._conn.write_register(
            unit=self._slave,
            address=(self._block_2_holding_regs['OPERATING MODE']['addr']),
            value=B2_OPERATING_MODE_WRITE.get(mode))

#    @property
#    def get_fan_speed(self):
#        """Return the current fan speed (0-4)."""
#        if self._update_on_read:
#            self.update()
#        return self._current_fan

#    @property
#    def get_heat_recovery(self):
#        """Return current heat recovery percentage."""
#        if self._update_on_read:
#            self.update()
#        return self._heat_recovery

#    @property
#    def get_heating(self):
#        """Return heater percentage."""
#        if self._update_on_read:
#            self.update()
#        return self._heating

#    @property
#    def get_heater_enabled(self):
#        """Return heater enabled."""
#        if self._update_on_read:
#            self.update()
#        return self._heater_enabled

#    @property
#    def get_cooling(self):
#        """Cooling active percentage."""
#        if self._update_on_read:
#            self.update()
#        return self._cooling

    @property
    def get_filter_alarm(self):
        """Change filter alarm."""
        if self._update_on_read:
            self.update()
        return self._filter_alarm
