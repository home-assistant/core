"""
Support for ADS binary sensors.

"""
import logging
import struct

import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDevice, \
    PLATFORM_SCHEMA, DEVICE_CLASSES_SCHEMA
from homeassistant.components import ads
from homeassistant.const import CONF_NAME, CONF_DEVICE_CLASS
import homeassistant.helpers.config_validation as cv


_LOGGER = logging.getLogger(__name__)


DEPENDENCIES = ['ads']
DEFAULT_NAME = 'ADS binary sensor'

CONF_ADSVAR = 'adsvar'


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADSVAR): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Set up the Binary Sensor platform for ADS. """
    adsvar = config.get(CONF_ADSVAR)
    name = config.get(CONF_NAME)
    device_class = config.get(CONF_DEVICE_CLASS)

    add_devices([AdsBinarySensor(name, adsvar, device_class)])


class AdsBinarySensor(ads.AdsDevice, BinarySensorDevice):
    """ Representation of ADS binary sensors. """

    def __init__(self, name, adsvar, device_class):
        ads.AdsDevice.__init__(self)

        self._name = name
        self._state = False
        self._device_class = device_class
        self.adsvar = adsvar
        self.adstype = ads.PLCTYPE_BOOL

        self.add_bool_device_notification(self.adsvar, self.bool_callback)

    @property
    def name(self):
        """ Return the default name of the binary sensor. """
        return self._name

    @property
    def device_class(self):
        """ Return the device class. """
        return self._device_class

    @property
    def in_on(self):
        """ Return if the binary sensor is on. """
        return self._state

    def bool_callback(self, name, value):
        self._state = value
        self.schedule_update_ha_state()
