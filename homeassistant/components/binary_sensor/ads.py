"""
Support for ADS binary sensors.

For more details about this platform, please refer to the documentation.
https://home-assistant.io/components/binary_sensor.ads/

"""

import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDevice, \
    PLATFORM_SCHEMA, DEVICE_CLASSES_SCHEMA
from homeassistant.components.ads import DATA_ADS, CONF_ADS_VAR, \
    CONF_ADS_USE_NOTIFY, CONF_ADS_POLL_INTERVAL
from homeassistant.const import CONF_NAME, CONF_DEVICE_CLASS
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.helpers.config_validation as cv


_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['ads']
DEFAULT_NAME = 'ADS binary sensor'


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADS_VAR): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_ADS_USE_NOTIFY): cv.boolean,
    vol.Optional(CONF_ADS_POLL_INTERVAL): cv.positive_int,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Binary Sensor platform for ADS."""
    ads_hub = hass.data.get(DATA_ADS)

    ads_var = config.get(CONF_ADS_VAR)
    name = config.get(CONF_NAME)
    device_class = config.get(CONF_DEVICE_CLASS)
    use_notify = config.get(CONF_ADS_USE_NOTIFY, ads_hub.use_notify)
    poll_interval = config.get(CONF_ADS_POLL_INTERVAL, ads_hub.poll_interval)

    ads_sensor = AdsBinarySensor(ads_hub, name, ads_var, device_class,
                                 use_notify, poll_interval)
    add_devices([ads_sensor])

    if use_notify:
        ads_hub.add_device_notification(ads_var, ads_hub.PLCTYPE_BOOL,
                                        ads_sensor.callback)
    else:
        dtime = timedelta(0, 0, poll_interval * 1000)
        async_track_time_interval(hass, ads_sensor.poll, dtime)


class AdsBinarySensor(BinarySensorDevice):
    """Representation of ADS binary sensors."""

    def __init__(self, ads_hub, name, ads_var, device_class, use_notify,
                 poll_interval):
        """Initialize AdsBinarySensor entity."""
        self._name = name
        self._state = False
        self._device_class = device_class or 'moving'
        self._ads_hub = ads_hub
        self.ads_var = ads_var
        self.use_notify = use_notify
        self.poll_interval = poll_interval

        # make first poll if notifications disabled
        if not self.use_notify:
            self.poll(None)

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

    def poll(self, now):
        """Handle polling."""
        try:
            self._state = self._ads_hub.read_by_name(
                self.ads_var, self._ads_hub.PLCTYPE_BOOL
            )
            _LOGGER.debug('Polled value for bool variable %s: %d',
                          self.ads_var, self._state)
        except self._ads_hub.ADSError as err:
            _LOGGER.error(err)
