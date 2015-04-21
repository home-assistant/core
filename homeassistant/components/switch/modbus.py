"""
Support for Modbus switches.

Configuration:
To use the Modbus switches you will need to add something like the following to
your config/configuration.yaml

sensor:
    platform: modbus
    slave: 1
    registers:
        24:
            bits:
                0:
                    name: My switch
                2:
                    name: My other switch

VARIABLES:

    - "slave" = slave number (ignored and can be omitted if not serial Modbus)
    - "registers" contains a list of relevant registers to read from
    - it must contain a "bits" section, listing relevant bits

    - each named bit will create a switch
"""

import logging

import homeassistant.components.modbus as modbus
from homeassistant.helpers.entity import ToggleEntity

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Read config and create Modbus devices """
    switches = []
    slave = config.get("slave", None)
    if modbus.TYPE == "serial" and not slave:
        _LOGGER.error("No slave number provided for serial Modbus")
        return False
    registers = config.get("registers")
    for regnum, register in registers.items():
        bits = register.get("bits")
        for bitnum, bit in bits.items():
            if bit.get("name"):
                switches.append(ModbusSwitch(bit.get("name"),
                                             slave,
                                             regnum,
                                             bitnum))
    add_devices(switches)


class ModbusSwitch(ToggleEntity):
    """ Represents a Modbus Switch """

    def __init__(self, name, slave, register, bit):
        self._name = name
        self.slave = int(slave) if slave else 1
        self.register = int(register)
        self.bit = int(bit)
        self._is_on = None
        self.register_value = None

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
        return "MODBUS-SWITCH-{}-{}-{}".format(self.slave,
                                               self.register,
                                               self.bit)

    @property
    def is_on(self):
        """ Returns True if switch is on. """
        return self._is_on

    @property
    def name(self):
        """ Get the name of the switch. """
        return self._name

    @property
    def state_attributes(self):
        attr = super().state_attributes
        return attr

    def turn_on(self, **kwargs):
        if self.register_value is None:
            self.update()
        val = self.register_value | (0x0001 << self.bit)
        modbus.NETWORK.write_register(unit=self.slave,
                                      address=self.register,
                                      value=val)

    def turn_off(self, **kwargs):
        if self.register_value is None:
            self.update()
        val = self.register_value & ~(0x0001 << self.bit)
        modbus.NETWORK.write_register(unit=self.slave,
                                      address=self.register,
                                      value=val)

    def update(self):
        result = modbus.NETWORK.read_holding_registers(unit=self.slave,
                                                       address=self.register,
                                                       count=1)
        val = 0
        for i, res in enumerate(result.registers):
            val += res * (2**(i*16))
        self.register_value = val
        self._is_on = (val & (0x0001 << self.bit) > 0)
