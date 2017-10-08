"""
Support for ADS binary sensors.

"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDevice, \
    PLATFORM_SCHEMA, DEVICE_CLASSES_SCHEMA, STATE_ON
from homeassistant.components.ads import DATA_ADS, PLCTYPE_BOOL, \
    CONF_ADSVAR, CONF_ADS_USE_NOTIFY, CONF_ADS_POLL_INTERVAL
from homeassistant.const import CONF_NAME, CONF_DEVICE_CLASS
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.helpers.config_validation as cv


_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['ads']
DEFAULT_NAME = 'ADS binary sensor'


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADSVAR): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_ADS_USE_NOTIFY, default=True): cv.boolean,
    vol.Optional(CONF_ADS_POLL_INTERVAL, default=1000): cv.positive_int,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Set up the Binary Sensor platform for ADS. """
    ads_hub = hass.data.get(DATA_ADS)
    if not ads_hub:
        return False

    adsvar = config.get(CONF_ADSVAR)
    name = config.get(CONF_NAME)
    device_class = config.get(CONF_DEVICE_CLASS)
    use_notify = config.get(CONF_ADS_USE_NOTIFY)
    poll_interval = config.get(CONF_ADS_POLL_INTERVAL)

    ads_sensor = AdsBinarySensor(ads_hub, name, adsvar, device_class,
                                 use_notify, poll_interval)
    add_devices([ads_sensor])

    if use_notify:
        ads_hub.add_device_notification(adsvar, PLCTYPE_BOOL,
                                        ads_sensor.callback)
    else:
        dtime = timedelta(0, 0, poll_interval * 1000)
        async_track_time_interval(hass, ads_sensor.poll, dtime)


class AdsBinarySensor(BinarySensorDevice):
    """ Representation of ADS binary sensors. """

    def __init__(self, ads_hub, name, adsvar, device_class, use_notify,
                 poll_interval):
        self._name = name
        self._state = False
        self._device_class = device_class or 'moving'
        self._ads_hub = ads_hub
        self.adsvar = adsvar
        self.use_notify = use_notify
        self.poll_interval = poll_interval

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

    def poll(self, now):
        self._state = self._ads_hub.read_by_name(self.adsvar, PLCTYPE_BOOL)
        _LOGGER.debug('Polled value for bool variable {0}: {1}'
                      .format(self.adsvar, self._state))
        try:
            self.schedule_update_ha_state()
        except AttributeError:
            pass
