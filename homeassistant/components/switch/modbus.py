"""
Support for Modbus switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.modbus/
"""
import logging

import homeassistant.components.modbus as modbus
from homeassistant.helpers.entity import ToggleEntity

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['modbus']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Read configuration and create Modbus devices."""
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
    """Representation of a Modbus switch."""

    # pylint: disable=too-many-arguments
    def __init__(self, name, slave, register, bit, coil=False):
        """Initialize the switch."""
        self._name = name
        self.slave = int(slave) if slave else 1
        self.register = int(register)
        self.bit = int(bit)
        self._coil = coil
        self._is_on = None
        self.register_value = None

    def __str__(self):
        """String representation of Modbus switch."""
        return "%s: %s" % (self.name, self.state)

    @property
    def should_poll(self):
        """Poling needed.

        Slaves are not allowed to initiate communication on Modbus networks.
        """
        return True

    @property
    def unique_id(self):
        """Return a unique ID."""
        return "MODBUS-SWITCH-{}-{}-{}".format(self.slave,
                                               self.register,
                                               self.bit)

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._is_on

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    def turn_on(self, **kwargs):
        """Set switch on."""
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
        """Set switch off."""
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
        """Update the state of the switch."""
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
