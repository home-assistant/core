"""
Support for controlling smbus (I2C) on supported platforms.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/smbus/
"""
# pylint: disable=import-error
import logging

REQUIREMENTS = ['smbus2==0.1.4']
DOMAIN = "rpi_i2c"
_LOGGER = logging.getLogger(__name__)
BUS = None


# pylint: disable=no-member
def setup(hass, config):
    import smbus2 as smbus
    global BUS
    revision = ([l[12:-1] for l in open('/proc/cpuinfo', 'r').readlines() if l[:8] == "Revision"] + ['0000'])[0]
    BUS = smbus.SMBus(1 if int(revision, 16) >= 4 else 0)
    _LOGGER.debug("RasPi revision is {0}".format((revision)))
    return True


def write_byte_data(addr, register, value):
    """Write byte to device."""
    BUS.write_byte_data(addr, register, value)


def read_i2c_block_data(addr, register, length):
    """read bytes from device."""
    return BUS.read_i2c_block_data(addr, register, length)

