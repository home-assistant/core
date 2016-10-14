"""
Support for EnOcean binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.enocean/
"""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA, SENSOR_CLASSES_SCHEMA)
from homeassistant.components import enocean
from homeassistant.const import (CONF_NAME, CONF_ID, CONF_SENSOR_CLASS)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['enocean']
DEFAULT_NAME = 'EnOcean binary sensor'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SENSOR_CLASS, default=None): SENSOR_CLASSES_SCHEMA,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Binary Sensor platform fo EnOcean."""
    dev_id = config.get(CONF_ID)
    devname = config.get(CONF_NAME)
    sensor_class = config.get(CONF_SENSOR_CLASS)

    add_devices([EnOceanBinarySensor(dev_id, devname, sensor_class)])


class EnOceanBinarySensor(enocean.EnOceanDevice, BinarySensorDevice):
    """Representation of EnOcean binary sensors such as wall switches."""

    def __init__(self, dev_id, devname, sensor_class):
        """Initialize the EnOcean binary sensor."""
        enocean.EnOceanDevice.__init__(self)
        self.stype = "listener"
        self.dev_id = dev_id
        self.which = -1
        self.onoff = -1
        self.devname = devname
        self._sensor_class = sensor_class

    @property
    def name(self):
        """The default name for the binary sensor."""
        return self.devname

    @property
    def sensor_class(self):
        """Return the class of this sensor."""
        return self._sensor_class

    def value_changed(self, value, value2):
        """Fire an event with the data that have changed.

        This method is called when there is an incoming packet associated
        with this platform.
        """
        self.update_ha_state()
        if value2 == 0x70:
            self.which = 0
            self.onoff = 0
        elif value2 == 0x50:
            self.which = 0
            self.onoff = 1
        elif value2 == 0x30:
            self.which = 1
            self.onoff = 0
        elif value2 == 0x10:
            self.which = 1
            self.onoff = 1
        self.hass.bus.fire('button_pressed', {"id": self.dev_id,
                                              'pushed': value,
                                              'which': self.which,
                                              'onoff': self.onoff})
