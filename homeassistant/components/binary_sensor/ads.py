"""
Support for ADS binary sensors.

"""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDevice, \
    PLATFORM_SCHEMA, DEVICE_CLASSES_SCHEMA, STATE_ON
from homeassistant.components.ads import DATA_ADS, PLCTYPE_BOOL
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
    ads_hub = hass.data.get(DATA_ADS)
    if not ads_hub:
        return False

    adsvar = config.get(CONF_ADSVAR)
    name = config.get(CONF_NAME)
    device_class = config.get(CONF_DEVICE_CLASS)

    add_devices([AdsBinarySensor(ads_hub, name, adsvar, device_class)])


class AdsBinarySensor(BinarySensorDevice):
    """ Representation of ADS binary sensors. """

    def __init__(self, ads_hub, name, adsvar, device_class):
        self._name = name
        self._state = False
        self._device_class = device_class or 'moving'
        self._ads_hub = ads_hub
        self.adsvar = adsvar

        self._ads_hub.add_device_notification(self.adsvar, PLCTYPE_BOOL,
                                              self.callback)

    @property
    def name(self):
        """ Return the default name of the binary sensor. """
        return self._name

    @property
    def device_class(self):
        """ Return the device class. """
        return self._device_class

    @property
    def is_on(self):
        """ Return if the binary sensor is on. """
        return self._state

    def callback(self, name, value):
        _LOGGER.debug('Variable "{0}" changed its value to "{1}"'
                      .format(name, value))
        self._state = value
        try:
            self.schedule_update_ha_state()
        except AttributeError:
            pass
