"""
Support for ADS sensors.

For more details about this platform, please refer to the documentation.
https://home-assistant.io/components/sensor.ads/

"""
import logging
from datetime import timedelta
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.components import ads
from homeassistant.components.ads import CONF_ADS_VAR, CONF_ADS_TYPE, \
    CONF_ADS_USE_NOTIFY, CONF_ADS_POLL_INTERVAL, CONF_ADS_FACTOR

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'ADS sensor'
DEPENDENCIES = ['ads']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADS_VAR): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=''): cv.string,
    vol.Optional(CONF_ADS_TYPE, default=ads.ADSTYPE_INT): vol.In(
        [ads.ADSTYPE_INT, ads.ADSTYPE_UINT, ads.ADSTYPE_BYTE]
    ),
    vol.Optional(CONF_ADS_USE_NOTIFY): cv.boolean,
    vol.Optional(CONF_ADS_POLL_INTERVAL): cv.positive_int,
    vol.Optional(CONF_ADS_FACTOR): cv.positive_int,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up an ADS sensor device."""
    ads_hub = hass.data.get(ads.DATA_ADS)

    ads_var = config.get(CONF_ADS_VAR)
    ads_type = config.get(CONF_ADS_TYPE)
    name = config.get(CONF_NAME)
    unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
    use_notify = config.get(CONF_ADS_USE_NOTIFY, ads_hub.use_notify)
    poll_interval = config.get(CONF_ADS_POLL_INTERVAL, ads_hub.poll_interval)
    factor = config.get(CONF_ADS_FACTOR)

    entity = AdsSensor(ads_hub, ads_var, ads_type, name,
                       unit_of_measurement, use_notify, poll_interval, factor)

    add_devices([entity])

    if use_notify:
        ads_hub.add_device_notification(ads_var, ads_hub.ADS_TYPEMAP[ads_type],
                                        entity.callback)
    else:
        dtime = timedelta(0, 0, poll_interval * 1000)
        async_track_time_interval(hass, entity.poll, dtime)


class AdsSensor(Entity):
    """Representation of an ADS sensor entity."""

    def __init__(self, ads_hub, ads_var, ads_type, name, unit_of_measurement,
                 use_notify, poll_interval, factor):
        """Initialize AdsSensor entity."""
        self._ads_hub = ads_hub
        self._name = name
        self._value = None
        self._unit_of_measurement = unit_of_measurement
        self.ads_var = ads_var
        self.ads_type = ads_type
        self.use_notify = use_notify
        self.poll_interval = poll_interval
        self.factor = factor

        # make first poll if notifications disabled
        if not self.use_notify:
            self.poll(None)

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    def callback(self, name, value):
        """Handle device notifications."""
        _LOGGER.debug('Variable %s changed its value to %d', name, value)

        # if factor is set use it otherwise not
        if self.factor is None:
            self._value = value
        else:
            self._value = value / self.factor

        try:
            self.schedule_update_ha_state()
        except AttributeError:
            pass

    def poll(self, now):
        """Poll value from ADS device."""
        try:
            val = self._ads_hub.read_by_name(
                self.ads_var, self._ads_hub.ADS_TYPEMAP[self.ads_type]
            )

            if self.factor is None:
                self._value = val
            else:
                self._value = val / self.factor

            _LOGGER.debug('Polled value for variable %s: %d',
                          self.ads_var, self._value)

        except self._ads_hub.ADSError as err:
            _LOGGER.error(err)

        try:
            self.schedule_update_ha_state()
        except AttributeError:
            pass
