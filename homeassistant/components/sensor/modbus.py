"""
Support for Modbus sensors.

Configuration:
To use the Modbus sensors you will need to add something like the following to
your config/configuration.yaml

sensor:
    platform: modbus
    slave: 1
    registers:
        16:
            name: My integer sensor
            unit: C
        24:
            bits:
                0:
                    name: My boolean sensor
                2:
                    name: My other boolean sensor

VARIABLES:

    - "slave" = slave number (ignored and can be omitted if not serial Modbus)
    - "unit" = unit to attach to value (optional, ignored for boolean sensors)
    - "registers" contains a list of relevant registers to read from
      it can contain a "bits" section, listing relevant bits

    - each named register will create an integer sensor
    - each named bit will create a boolean sensor
"""

import logging

import homeassistant.components.modbus as modbus
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    TEMP_CELCIUS, TEMP_FAHRENHEIT,
    STATE_ON, STATE_OFF)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Read config and create Modbus devices """
    sensors = []
    slave = config.get("slave", None)
    if modbus.TYPE == "serial" and not slave:
        _LOGGER.error("No slave number provided for serial Modbus")
        return False
    registers = config.get("registers")
    for regnum, register in registers.items():
        if register.get("name"):
            sensors.append(ModbusSensor(register.get("name"),
                                        slave,
                                        regnum,
                                        None,
                                        register.get("unit")))
        if register.get("bits"):
            bits = register.get("bits")
            for bitnum, bit in bits.items():
                if bit.get("name"):
                    sensors.append(ModbusSensor(bit.get("name"),
                                                slave,
                                                regnum,
                                                bitnum))
    add_devices(sensors)


class ModbusSensor(Entity):
    # pylint: disable=too-many-arguments
    """ Represents a Modbus Sensor """

    def __init__(self, name, slave, register, bit=None, unit=None):
        self._name = name
        self.slave = int(slave) if slave else 1
        self.register = int(register)
        self.bit = int(bit) if bit else None
        self._value = None
        self._unit = unit

    def __str__(self):
        return "%s: %s" % (self.name, self.state)

    @property
    def should_poll(self):
        """ We should poll, because slaves are not allowed to
            initiate communication on Modbus networks"""
        return True

    @property
    def unique_id(self):
        """ Returns a unique id. """
        return "MODBUS-SENSOR-{}-{}-{}".format(self.slave,
                                               self.register,
                                               self.bit)

    @property
    def state(self):
        """ Returns the state of the sensor. """
        if self.bit:
            return STATE_ON if self._value else STATE_OFF
        else:
            return self._value

    @property
    def name(self):
        """ Get the name of the sensor. """
        return self._name

    @property
    def unit_of_measurement(self):
        """ Unit of measurement of this entity, if any. """
        if self._unit == "C":
            return TEMP_CELCIUS
        elif self._unit == "F":
            return TEMP_FAHRENHEIT
        else:
            return self._unit

    @property
    def state_attributes(self):
        attr = super().state_attributes
        return attr

    def update(self):
        result = modbus.NETWORK.read_holding_registers(unit=self.slave,
                                                       address=self.register,
                                                       count=1)
        val = 0
        for i, res in enumerate(result.registers):
            val += res * (2**(i*16))
        if self.bit:
            self._value = val & (0x0001 << self.bit)
        else:
            self._value = val
