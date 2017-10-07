"""
Support for ADS sensors.__init__.py

"""
import logging
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.components import ads

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'ADS sensor'
DEPENDENCIES = ['ads']

CONF_ADSVAR = 'adsvar'
CONF_ADSTYPE = 'adstype'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADSVAR): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=''): cv.string,
    vol.Optional(CONF_ADSTYPE, default=ads.ADSTYPE_INT): vol.In(
        [ads.ADSTYPE_INT, ads.ADSTYPE_UINT, ads.ADSTYPE_BYTE]
    ),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Set up an ADS sensor device. """
    ads_hub = hass.data.get(ads.DATA_ADS)
    if not ads_hub:
        return False

    adsvar = config.get(CONF_ADSVAR)
    adstype = config.get(CONF_ADSTYPE)
    name = config.get(CONF_NAME)
    unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)

    add_devices([AdsSensor(ads_hub, adsvar, adstype, name,
                           unit_of_measurement)])


class AdsSensor(Entity):

    def __init__(self, ads_hub, adsvar, adstype, devname, unit_of_measurement):
        self._ads_hub = ads_hub
        self._name = devname
        self._value = 0
        self._unit_of_measurement = unit_of_measurement
        self.adsvar = adsvar
        self.adstype = adstype

        self._ads_hub.add_device_notification(
            self.adsvar, ads.ADS_TYPEMAP[adstype], self.callback)

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        """ Return the state of the device. """
        return self._value

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement

    def callback(self, name, value):
        _LOGGER.debug('Variable "{0}" changed its value to "{1}"'
                      .format(name, value))
        self._value = value
        try:
            self.schedule_update_ha_state()
        except AttributeError:
            pass
