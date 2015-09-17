"""
homeassistant.components.switch.modbus
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Modbus switches.

Configuration:

To use the Modbus switches you will need to add something like the following to
your configuration.yaml file.

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
    coils:
        0:
            name: My coil switch

VARIABLES:

    - "slave" = slave number (ignored and can be omitted if not serial Modbus)
    - "registers" contains a list of relevant registers to read from
    - it must contain a "bits" section, listing relevant bits
    - "coils" contains a list of relevant coils to read from/write to

    - each named bit will create a switch
"""

import logging

import homeassistant.components.modbus as modbus
from homeassistant.helpers.entity import ToggleEntity

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['modbus']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Read configuration and create Modbus devices. """
    switches = []
    slave = config.get("slave", None)
    if modbus.TYPE == "serial" and not slave:
        _LOGGER.error("No slave number provided for serial Modbus")
        return False
    registers = config.get("registers")
    if registers:
        for regnum, register in registers.items():
            bits = register.get("bits")
            for bitnum, bit in bits.items():
                if bit.get("name"):
                    switches.append(ModbusSwitch(bit.get("name"),
                                                 slave,
                                                 regnum,
                                                 bitnum))
    coils = config.get("coils")
    if coils:
        for coilnum, coil in coils.items():
            switches.append(ModbusSwitch(coil.get("name"),
                                         slave,
                                         coilnum,
                                         0,
                                         coil=True))
    add_devices(switches)


class ModbusSwitch(ToggleEntity):
    # pylint: disable=too-many-arguments
    """ Represents a Modbus switch. """

    def __init__(self, name, slave, register, bit, coil=False):
        self._name = name
        self.slave = int(slave) if slave else 1
        self.register = int(register)
        self.bit = int(bit)
        self._coil = coil
        self._is_on = None
        self.register_value = None

    def __str__(self):
        return "%s: %s" % (self.name, self.state)

    @property
    def should_poll(self):
        """
        We should poll, because slaves are not allowed to initiate
        communication on Modbus networks.
        """
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

    def turn_on(self, **kwargs):
        """ Set switch on. """
        if self.register_value is None:
            self.update()

        if self._coil:
            modbus.NETWORK.write_coil(self.register, True)
        else:
            val = self.register_value | (0x0001 << self.bit)
            modbus.NETWORK.write_register(unit=self.slave,
                                          address=self.register,
                                          value=val)

    def turn_off(self, **kwargs):
        """ Set switch off. """
        if self.register_value is None:
            self.update()

        if self._coil:
            modbus.NETWORK.write_coil(self.register, False)
        else:
            val = self.register_value & ~(0x0001 << self.bit)
            modbus.NETWORK.write_register(unit=self.slave,
                                          address=self.register,
                                          value=val)

    def update(self):
        """ Update the state of the switch. """
        if self._coil:
            result = modbus.NETWORK.read_coils(self.register, 1)
            self.register_value = result.bits[0]
            self._is_on = self.register_value
        else:
            result = modbus.NETWORK.read_holding_registers(
                unit=self.slave, address=self.register,
                count=1)
            val = 0
            for i, res in enumerate(result.registers):
                val += res * (2**(i*16))
            self.register_value = val
            self._is_on = (val & (0x0001 << self.bit) > 0)
