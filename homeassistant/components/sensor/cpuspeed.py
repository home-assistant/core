"""
homeassistant.components.sensor.cpuspeed
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Shows the current CPU speed.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.cpuspeed/
"""
import logging

from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['py-cpuinfo==0.1.6']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "CPU speed"

ATTR_VENDOR = 'Vendor ID'
ATTR_BRAND = 'Brand'
ATTR_HZ = 'GHz Advertised'


# pylint: disable=unused-variable
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the CPU speed sensor. """

    try:
        import cpuinfo  # noqa
    except ImportError:
        _LOGGER.exception(
            "Unable to import cpuinfo. "
            "Did you maybe not install the 'py-cpuinfo' package?")
        return False

    add_devices([CpuSpeedSensor(config.get('name', DEFAULT_NAME))])


class CpuSpeedSensor(Entity):
    """ A CPU info sensor. """

    def __init__(self, name):
        self._name = name
        self._state = None
        self._unit_of_measurement = 'GHz'
        self.update()

    @property
    def name(self):
        """ The name of the sensor. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def unit_of_measurement(self):
        """ Unit the value is expressed in. """
        return self._unit_of_measurement

    @property
    def state_attributes(self):
        """ Returns the state attributes. """
        if self.info is not None:
            return {
                ATTR_VENDOR: self.info['vendor_id'],
                ATTR_BRAND: self.info['brand'],
                ATTR_HZ: round(self.info['hz_advertised_raw'][0]/10**9, 2)
            }

    def update(self):
        """ Gets the latest data and updates the state. """
        from cpuinfo import cpuinfo

        self.info = cpuinfo.get_cpu_info()
        self._state = round(float(self.info['hz_actual_raw'][0])/10**9, 2)
