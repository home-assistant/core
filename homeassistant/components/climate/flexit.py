"""
Platform for Flexit AC units with CI66 Modbus adapter.

Example configuration:

climate:
  - platform: flexit
    name: Main AC
    slave: 21

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/climate.flexit/
"""
import logging
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_SLAVE, TEMP_CELSIUS,
    ATTR_TEMPERATURE, DEVICE_DEFAULT_NAME)
from homeassistant.components.climate import (ClimateDevice, PLATFORM_SCHEMA)
import homeassistant.components.modbus as modbus
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['modbus']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SLAVE): vol.All(int, vol.Range(min=0, max=32)),
    vol.Optional(CONF_NAME, default=DEVICE_DEFAULT_NAME): cv.string
})

_LOGGER = logging.getLogger(__name__)

REGMAP_INPUT = {
    'GWYVer':                   {'addr':   0, 'value': 0},
    'CUHWType':                 {'addr':   1, 'value': 0},
    'CUSWRev':                  {'addr':   2, 'value': 0},
    'CPASWRev':                 {'addr':   3, 'value': 0},
    'CPB1SWRev':                {'addr':   4, 'value': 0},
    'CBPS2WRev':                {'addr':   5, 'value': 0},
    'Time1H':                   {'addr':   6, 'value': 0},
    'Time1L':                   {'addr':   7, 'value': 0},
    'FilterTimer':              {'addr':   8, 'value': 0},
    'SupplyAirTemp':            {'addr':   9, 'value': 0},
    'ExtractAirTemp':           {'addr':  10, 'value': 0},
    'OutdoorAirTemp':           {'addr':  11, 'value': 0},
    'ReturnWaterTemp':          {'addr':  12, 'value': 0},
    'Cooling':                  {'addr':  13, 'value': 0},
    'HeatExchanger':            {'addr':  14, 'value': 0},
    'Heating':                  {'addr':  15, 'value': 0},
    'RegulationFanSpeed':       {'addr':  16, 'value': 0},
    'OperTime':                 {'addr':  17, 'value': 0},
    'FilterResetNo':            {'addr':  18, 'value': 0},
    'SupplyAirAlarm':           {'addr':  19, 'value': 0},
    'ExtractAirAlarm':          {'addr':  20, 'value': 0},
    'OutsideAirAlarm':          {'addr':  21, 'value': 0},
    'ReturnWaterAlarm':         {'addr':  22, 'value': 0},
    'FireThermostatAlarm':      {'addr':  23, 'value': 0},
    'FireSmokeAlarm':           {'addr':  24, 'value': 0},
    'FreezeProtectionAlarm':    {'addr':  25, 'value': 0},
    'RotorAlarm':               {'addr':  26, 'value': 0},
    'ReplaceFilterAlarm':       {'addr':  27, 'value': 0},
    'HeatingBatteryActive':     {'addr':  28, 'value': 0},
    'SchActive':                {'addr':  29, 'value': 0},
    'SP0TimeH':                 {'addr':  30, 'value': 0},
    'SP0TimeL':                 {'addr':  31, 'value': 0},
    'SP1TimeH':                 {'addr':  32, 'value': 0},
    'SP1TimeL':                 {'addr':  33, 'value': 0},
    'SP2TimeH':                 {'addr':  34, 'value': 0},
    'SP2TimeL':                 {'addr':  35, 'value': 0},
    'SP3TimeH':                 {'addr':  36, 'value': 0},
    'SP3TimeL':                 {'addr':  37, 'value': 0},
    'VVX1TimeH':                {'addr':  38, 'value': 0},
    'VVX1TimeL':                {'addr':  39, 'value': 0},
    'EV1TimeH':                 {'addr':  40, 'value': 0},
    'EV1TimeL':                 {'addr':  41, 'value': 0},
    'OperTimeH':                {'addr':  42, 'value': 0},
    'OperTimeL':                {'addr':  43, 'value': 0},
    'FilterTimeH':              {'addr':  44, 'value': 0},
    'FilterTimeL':              {'addr':  45, 'value': 0},
    'FilterAlarmPeriod':        {'addr':  46, 'value': 0},
    'ActualSetAirTemperature':  {'addr':  47, 'value': 0},
    'ActualSetAirSpeed':        {'addr':  48, 'value': 0}
}
REGMAP_HOLDING = {
    'SupplyAirSpeed1':          {'addr':  0, 'value': 0},
    'SupplyAirSpeed2':          {'addr':  1, 'value': 0},
    'SupplyAirSpeed3':          {'addr':  2, 'value': 0},
    'SupplyAirSpeed4':          {'addr':  3, 'value': 0},
    'ExtractAirSpeed1':         {'addr':  4, 'value': 0},
    'ExtractAirSpeed2':         {'addr':  5, 'value': 0},
    'ExtractAirSpeed3':         {'addr':  6, 'value': 0},
    'ExtractAirSpeed4':         {'addr':  7, 'value': 0},
    'SetAirTemperature':        {'addr':  8, 'value': 0},
    'SupplyAirMinTemp':         {'addr':  9, 'value': 0},
    'SupplyAirMaxTemp':         {'addr': 10, 'value': 0},
    'CoolingOutdoorAirMinTemp': {'addr': 11, 'value': 0},
    'ForcedVentSpeed':          {'addr': 12, 'value': 0},
    'ForcedVentTime':           {'addr': 13, 'value': 0},
    'AirRegulationType':        {'addr': 14, 'value': 0},
    'CoolingActive':            {'addr': 15, 'value': 0},
    'ForcedVentilation':        {'addr': 16, 'value': 0},
    'SetAirSpeed':              {'addr': 17, 'value': 0},
    'TimeH':                    {'addr': 18, 'value': 0},
    'TimeL':                    {'addr': 19, 'value': 0},
    'Unknown1':                 {'addr': 20, 'value': 0},
    'FireSmokeMode':            {'addr': 21, 'value': 0}
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Flexit Platform."""
    modbus_slave = config.get(CONF_SLAVE, None)
    name = config.get(CONF_NAME, None)
    add_devices([Flexit(modbus_slave, name)], True)


class Flexit(ClimateDevice):
    """Representation of a Flexit AC unit."""

    def __init__(self, modbus_slave, name):
        """Initialize the unit."""
        self._name = name
        self._input_regs = REGMAP_INPUT
        self._holding_regs = REGMAP_HOLDING
        self._slave = modbus_slave
        self._target_temperature = None
        self._current_temperature = None
        self._current_fan_mode = None
        self._current_operation = None
        self._fan_list = ['Off', 'Low', 'Medium', 'High']
        self._current_operation = None
        self._filter_hours = None
        self._filter_alarm = None
        self._heat_recovery = None
        self._heater_enabled = False
        self._heating = None
        self._cooling = None
        self._alarm = False

    def update(self):
        """Read registers from unit and update states."""
        _LOGGER.debug('update() for %s called', self._name)

        try:
            result_input = modbus.HUB.read_input_registers(
                unit=self._slave,
                address=0,
                count=len(self._input_regs)).registers
            result_holding = modbus.HUB.read_holding_registers(
                unit=self._slave,
                address=0,
                count=len(self._holding_regs)).registers
        except AttributeError:
            # The unit does not reply reliably
            _LOGGER.warning('modbus read was unsuccessful for %s', self._name)
        else:
            for k in self._holding_regs:
                self._holding_regs[k]['value'] = \
                    result_holding[self._holding_regs[k]['addr']]
            for k in self._input_regs:
                self._input_regs[k]['value'] = \
                    result_input[self._input_regs[k]['addr']]

        self._target_temperature = \
            (self._input_regs['ActualSetAirTemperature']['value'] / 10.0)
        # Temperature directly after heat recovery and heater
        self._current_temperature = \
            (self._input_regs['SupplyAirTemp']['value'] / 10.0)
        self._current_fan_mode = \
            (self._fan_list[
                self._input_regs['ActualSetAirSpeed']['value']])
        # Hours since last filter reset
        self._filter_hours = \
            self._input_regs['FilterTimer']['value']
        # Mechanical heat recovery, 0-100%
        self._heat_recovery = \
            self._input_regs['HeatExchanger']['value']
        # Heater active 0-100%
        self._heating = \
            self._input_regs['Heating']['value']
        # Cooling active 0-100%
        self._cooling = \
            self._input_regs['Cooling']['value']
        # Filter alarm 0/1
        self._filter_alarm = \
            bool(self._input_regs['ReplaceFilterAlarm']['value'])
        # Heater enabled or not. Does not mean it's necessarily heating
        self._heater_enabled = \
            bool(self._input_regs['HeatingBatteryActive']['value'])
        # Current operation mode
        if self._heating:
            self._current_operation = 'Heating'
        elif self._cooling:
            self._current_operation = 'Cooling'
        elif self._heat_recovery:
            self._current_operation = 'Recovering'
        elif self._input_regs['ActualSetAirSpeed']['value']:
            self._current_operation = 'Fan Only'
        else:
            self._current_operation = 'Off'

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {
            'filter_hours':     self._filter_hours,
            'filter_alarm':     self._filter_alarm,
            'heat_recovery':    self._heat_recovery,
            'heating':          self._heating,
            'heater_enabled':   self._heater_enabled,
            'cooling':          self._cooling
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

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self._current_fan_mode

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return self._fan_list

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._target_temperature = kwargs.get(ATTR_TEMPERATURE)

        modbus.HUB.write_register(
            unit=self._slave,
            address=(self._holding_regs['SetAirTemperature']['addr']),
            value=round(self._target_temperature * 10.0))
        _LOGGER.debug("Setting temperature for %s to %f",
                      self._name, self._target_temperature)
        self.schedule_update_ha_state()

    def set_fan_mode(self, fan):
        """Set new fan mode."""
        modbus.HUB.write_register(
            unit=self._slave,
            address=(self._holding_regs['SetAirSpeed']['addr']),
            value=self._fan_list.index(fan))
        self._current_fan_mode = self._fan_list.index(fan)
        self.schedule_update_ha_state()
