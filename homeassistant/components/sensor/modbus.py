"""
Support for Modbus sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.modbus/
"""
import logging

import homeassistant.components.modbus as modbus
from homeassistant.const import (
    STATE_OFF, STATE_ON, TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['modbus']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Modbus devices."""
    sensors = []
    slave = config.get("slave", None)
    if modbus.TYPE == "serial" and not slave:
        _LOGGER.error("No slave number provided for serial Modbus")
        return False
    registers = config.get("registers")
    if registers:
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
    coils = config.get("coils")
    if coils:
        for coilnum, coil in coils.items():
            sensors.append(ModbusSensor(coil.get("name"),
                                        slave,
                                        coilnum,
                                        coil=True))

    add_devices(sensors)


class ModbusSensor(Entity):
    """Representation of a Modbus Sensor."""

    # pylint: disable=too-many-arguments
    def __init__(self, name, slave, register, bit=None, unit=None, coil=False):
        """Initialize the sensor."""
        self._name = name
        self.slave = int(slave) if slave else 1
        self.register = int(register)
        self.bit = int(bit) if bit else None
        self._value = None
        self._unit = unit
        self._coil = coil

    def __str__(self):
        """Return the name and the state of the sensor."""
        return "%s: %s" % (self.name, self.state)

    @property
    def should_poll(self):
        """Polling needed."""
        return True

    @property
    def unique_id(self):
        """Return a unique id."""
        return "MODBUS-SENSOR-{}-{}-{}".format(self.slave,
                                               self.register,
                                               self.bit)

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.bit:
            return STATE_ON if self._value else STATE_OFF
        else:
            return self._value

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if self._unit == "C":
            return TEMP_CELSIUS
        elif self._unit == "F":
            return TEMP_FAHRENHEIT
        else:
            return self._unit

    def update(self):
        """Update the state of the sensor."""
        if self._coil:
            result = modbus.NETWORK.read_coils(self.register, 1)
            self._value = result.bits[0]
        else:
            result = modbus.NETWORK.read_holding_registers(
                unit=self.slave, address=self.register,
                count=1)
            val = 0
            for i, res in enumerate(result.registers):
                val += res * (2**(i*16))
            if self.bit:
                self._value = val & (0x0001 << self.bit)
            else:
                self._value = val
