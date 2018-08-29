"""
Support to control a Salda Smarty XP/XV ventilation unit.

For more details about this component, please refer to the documentation at:
https://home-assistant.io/components/smarty/

MCB 1.21 Modbus Table:
http://salda.lt/mcb/downloads/doc/MCB%201.21%20Modbus%20table%202018-05-03.xlsx
"""

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components import modbus
from homeassistant.const import (CONF_NAME, CONF_SLAVE, TEMP_CELSIUS)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import track_time_interval

DEPENDENCIES = ['modbus']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'smarty'
DATA_SMARTY = 'smarty'

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({
            vol.Required(CONF_SLAVE): cv.positive_int,
            vol.Optional(CONF_NAME, default='Smarty'): cv.string
        }),
    },
    extra=vol.ALLOW_EXTRA)

RPM = 'rpm'
SIGNAL_UPDATE_SMARTY = 'smarty_update'

INPUT_REGS = {
    'IR_CURRENT_SYSTEM_STATE': {
        'ADDR': 1,
        'NAME': 'Current system state',
        'MULTIPLIER': 1,
        'STATE': {
            0: 'Stand-by',
            1: 'Building protection',
            2: 'Economy',
            3: 'Comfort',
            4: 'Emergency run',
            5: 'Preparing',
            6: 'Opening dampers',
            7: 'Boost',
            8: 'Cooling heaters',
            9: 'Closing dampers',
            10: 'Night Cooling',
            11: 'Critical alarm',
            12: 'Fire alarm',
            13: 'Heat exchanger frost protection',
            14: 'Change filters',
            15: 'Room RH 3 days average is lower than 30%. Limiting speed',
            16: 'DX cooler defrosting',
            17: 'Fire damper testing'
        },
        'UNIT_OF_MESUREMENT': None
    },
    'IR_CURRENT_SYSTEM_MODE': {
        'ADDR': 15,
        'NAME': 'Current system mode',
        'MULTIPLIER': 1,
        'STATE': {
            0: 'Stand-by',
            1: 'Building protection',
            2: 'Economy',
            3: 'Comfort',
            4: 'Boost'
        },
        'UNIT_OF_MESUREMENT': None
    },
    'IR_SUPPLY_AIR_TEMPERATURE': {
        'ADDR': 18,
        'NAME': 'T1-Supply air temperature',
        'MULTIPLIER': 0.1,
        'STATE': {},
        'UNIT_OF_MESUREMENT': TEMP_CELSIUS
    },
    'IR_EXTRACT_AIR_TEMPERATURE': {
        'ADDR': 19,
        'NAME': 'T2-Extract air temperature',
        'MULTIPLIER': 0.1,
        'STATE': {},
        'UNIT_OF_MESUREMENT': TEMP_CELSIUS
    },
    'IR_OUTDOOR_AIR_TEMPERATURE': {
        'ADDR': 21,
        'NAME': 'Outdoor air temperature',
        'MULTIPLIER': 0.1,
        'STATE': {},
        'UNIT_OF_MESUREMENT': TEMP_CELSIUS
    },
    'IR_SUPPLY_FAN_SPEED_RPM': {
        'ADDR': 55,
        'NAME': 'Supply fan spreed RPM',
        'MULTIPLIER': 1,
        'STATE': {},
        'UNIT_OF_MESUREMENT': RPM
    },
    'IR_EXTRACT_FAN_SPEED_RPM': {
        'ADDR': 56,
        'NAME': 'Extract fan spreed RPM',
        'MULTIPLIER': 1,
        'STATE': {},
        'UNIT_OF_MESUREMENT': RPM
    }
}

HOLDING_REGS = {
    'HR_USER_CONFIG_CURRENT_SYSTEM_MODE': {
        'ADDR': 1,
        'NAME': 'Current system mode',
        'STATE': {
            'Stand-by': 0,
            'Building protection': 1,
            'Economy': 2,
            'Confort': 3
        }
    }
}


def setup(hass, config):
    """Set up the smarty environment."""
    conf = config[DOMAIN]

    name = conf.get(CONF_NAME)
    modbus_slave = conf.get(CONF_SLAVE)

    _LOGGER.debug("name: %s, modbus_slave: %s", name, modbus_slave)

    smarty = Smarty(hass, name, modbus_slave)
    hass.data[DATA_SMARTY] = smarty

    # Load platforms
    discovery.load_platform(hass, 'fan', DOMAIN, {}, config)
    discovery.load_platform(hass, 'sensor', DOMAIN, {}, config)

    def poll_device_update(event_time):
        """Update Smarty device."""
        _LOGGER.debug("Updating Smarty device...")
        smarty.update()
        dispatcher_send(hass, SIGNAL_UPDATE_SMARTY)

    track_time_interval(hass, poll_device_update, timedelta(seconds=30))

    return True


class Smarty:
    """Representation of a Smarty Ventilation Unit."""

    def __init__(self, hass, name, modbus_slave):
        """Initialize the Smarty Ventilation Unit."""
        self.data = {}
        self.name = name
        self.hass = hass
        self._modbus_slave = modbus_slave
        self._holding_registers = []
        self._coils = []
        self._discrete_inputs = []
        self._input_registers = []

    def update(self):
        """Update registers."""
        from pymodbus.exceptions import ConnectionException
        try:
            result = modbus.HUB.read_holding_registers(unit=self._modbus_slave,
                                                       address=1,
                                                       count=37)
            self._holding_registers = result.registers
            _LOGGER.debug('Holding Registers: %s', self._holding_registers)

            # it cannot read all 132 registers at once
            result1 = modbus.HUB.read_input_registers(unit=self._modbus_slave,
                                                      address=1,
                                                      count=66)
            result2 = modbus.HUB.read_input_registers(unit=self._modbus_slave,
                                                      address=67,
                                                      count=66)
            self._input_registers = result1.registers + result2.registers
            _LOGGER.debug('Input Registers: %s', self._input_registers)
        except AttributeError:
            _LOGGER.error('No valid response from modbus slave %s',
                          self._modbus_slave)
        except ConnectionException:
            _LOGGER.error('Cannot connect to Smarty. Modbus Unreacheable.')

    def get_fan_mode(self):
        """Get Current System Mode."""
        addr = HOLDING_REGS['HR_USER_CONFIG_CURRENT_SYSTEM_MODE']['ADDR']
        return self._holding_registers[addr - 1]

    def set_fan_mode(self, mode):
        """Set Current System Mode."""
        from pymodbus.exceptions import ConnectionException
        _LOGGER.debug('Set System Mode to : %s', mode)
        try:
            addr = HOLDING_REGS['HR_USER_CONFIG_CURRENT_SYSTEM_MODE']['ADDR']
            modbus.HUB.write_register(self._modbus_slave, addr, mode)
        except ConnectionException:
            _LOGGER.error('Cannot connect to Smarty. Modbus Unreacheable.')

    def get_sensor(self, sensor_type):
        """Get a sensor value."""
        addr = INPUT_REGS[sensor_type]['ADDR']
        multiplier = INPUT_REGS[sensor_type]['MULTIPLIER']
        result = round(self._input_registers[addr - 1] * multiplier, 2)
        _LOGGER.debug('Get Sensor result: %s', result)
        return result
