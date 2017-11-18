"""Support for ADS binary sensors."""

import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDevice, \
    PLATFORM_SCHEMA, DEVICE_CLASSES_SCHEMA
from homeassistant.components.ads import DATA_ADS, CONF_ADSVAR
from homeassistant.const import CONF_NAME, CONF_DEVICE_CLASS
import homeassistant.helpers.config_validation as cv


_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['ads']
DEFAULT_NAME = 'ADS binary sensor'


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADSVAR): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Binary Sensor platform for ADS."""
    ads_hub = hass.data.get(DATA_ADS)
    if not ads_hub:
        return False

    adsvar = config.get(CONF_ADSVAR)
    name = config.get(CONF_NAME)
    device_class = config.get(CONF_DEVICE_CLASS)

    ads_sensor = AdsBinarySensor(ads_hub, name, adsvar, device_class)
    add_devices([ads_sensor], True)

    ads_hub.add_device_notification(adsvar, ads_hub.PLCTYPE_BOOL,
                                    ads_sensor.callback)


class AdsBinarySensor(BinarySensorDevice):
    """Representation of ADS binary sensors."""

    def __init__(self, ads_hub, name, adsvar, device_class):
        """Initialize AdsBinarySensor entity."""
        self._name = name
        self._state = False
        self._device_class = device_class or 'moving'
        self._ads_hub = ads_hub
        self.adsvar = adsvar

    @property
    def name(self):
        """Return the default name of the binary sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def is_on(self):
        """Return if the binary sensor is on."""
        return self._state

    def callback(self, name, value):
        """Handle device notifications."""
        _LOGGER.debug('Variable %s changed its value to %d',
                      name, value)
        self._state = value
        try:
            self.schedule_update_ha_state()
        except AttributeError:
            pass
