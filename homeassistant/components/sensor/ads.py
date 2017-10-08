"""
Support for ADS sensors.__init__.py

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
from homeassistant.components.ads import CONF_ADSVAR, CONF_ADSTYPE, \
    CONF_ADS_USE_NOTIFY, CONF_ADS_POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'ADS sensor'
DEPENDENCIES = ['ads']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADSVAR): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=''): cv.string,
    vol.Optional(CONF_ADSTYPE, default=ads.ADSTYPE_INT): vol.In(
        [ads.ADSTYPE_INT, ads.ADSTYPE_UINT, ads.ADSTYPE_BYTE]
    ),
    vol.Optional(CONF_ADS_USE_NOTIFY, default=True): cv.boolean,
    vol.Optional(CONF_ADS_POLL_INTERVAL, default=1000): cv.positive_int,
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
    use_notify = config.get(CONF_ADS_USE_NOTIFY)
    poll_interval = config.get(CONF_ADS_POLL_INTERVAL)

    entity = AdsSensor(ads_hub, adsvar, adstype, name,
                       unit_of_measurement, use_notify, poll_interval)

    add_devices([entity])

    if use_notify:
        ads_hub.add_device_notification(adsvar, ads.ADS_TYPEMAP[adstype],
                                        entity.callback)
    else:
        dtime = timedelta(0, 0, poll_interval * 1000)
        async_track_time_interval(hass, entity.poll, dtime)


class AdsSensor(Entity):

    def __init__(self, ads_hub, adsvar, adstype, devname, unit_of_measurement,
                 use_notify, poll_interval):
        self._ads_hub = ads_hub
        self._name = devname
        self._value = 0
        self._unit_of_measurement = unit_of_measurement
        self.adsvar = adsvar
        self.adstype = adstype
        self.use_notify = use_notify
        self.poll_interval = poll_interval

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

    def poll(self, now):
        self._value = self._ads_hub.read_by_name(
            self.adsvar, ads.ADS_TYPEMAP[self.adstype]
        )

        _LOGGER.debug('Polled value for bool variable {0}: {1}'
                      .format(self.adsvar, self._value))

        try:
            self.schedule_update_ha_state()
        except AttributeError:
            pass

