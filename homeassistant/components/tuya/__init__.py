"""Support for Tuya Smart devices."""
from datetime import timedelta
import logging
import voluptuous as vol

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, CONF_PLATFORM)
from homeassistant.helpers import discovery
from homeassistant.helpers.dispatcher import (
    dispatcher_send, async_dispatcher_connect)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

CONF_COUNTRYCODE = 'country_code'

DOMAIN = 'tuya'
DATA_TUYA = 'data_tuya'

SIGNAL_DELETE_ENTITY = 'tuya_delete'
SIGNAL_UPDATE_ENTITY = 'tuya_update'

SERVICE_FORCE_UPDATE = 'force_update'
SERVICE_PULL_DEVICES = 'pull_devices'

TUYA_TYPE_TO_HA = {
    'climate': 'climate',
    'cover': 'cover',
    'fan': 'fan',
    'light': 'light',
    'scene': 'scene',
    'switch': 'switch',
}

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_COUNTRYCODE): cv.string,
        vol.Optional(CONF_PLATFORM, default='tuya'): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up Tuya Component."""
    from tuyapy import TuyaApi

    tuya = TuyaApi()
    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    country_code = config[DOMAIN][CONF_COUNTRYCODE]
    platform = config[DOMAIN][CONF_PLATFORM]

    hass.data[DATA_TUYA] = tuya
    tuya.init(username, password, country_code, platform)
    hass.data[DOMAIN] = {
        'entities': {}
    }

    def load_devices(device_list):
        """Load new devices by device_list."""
        device_type_list = {}
        for device in device_list:
            dev_type = device.device_type()
            if (dev_type in TUYA_TYPE_TO_HA and
                    device.object_id() not in hass.data[DOMAIN]['entities']):
                ha_type = TUYA_TYPE_TO_HA[dev_type]
                if ha_type not in device_type_list:
                    device_type_list[ha_type] = []
                device_type_list[ha_type].append(device.object_id())
                hass.data[DOMAIN]['entities'][device.object_id()] = None
        for ha_type, dev_ids in device_type_list.items():
            discovery.load_platform(
                hass, ha_type, DOMAIN, {'dev_ids': dev_ids}, config)

    device_list = tuya.get_all_devices()
    load_devices(device_list)

    def poll_devices_update(event_time):
        """Check if accesstoken is expired and pull device list from server."""
        _LOGGER.debug("Pull devices from Tuya.")
        tuya.poll_devices_update()
        # Add new discover device.
        device_list = tuya.get_all_devices()
        load_devices(device_list)
        # Delete not exist device.
        newlist_ids = []
        for device in device_list:
            newlist_ids.append(device.object_id())
        for dev_id in list(hass.data[DOMAIN]['entities']):
            if dev_id not in newlist_ids:
                dispatcher_send(hass, SIGNAL_DELETE_ENTITY, dev_id)
                hass.data[DOMAIN]['entities'].pop(dev_id)

    track_time_interval(hass, poll_devices_update, timedelta(minutes=5))

    hass.services.register(DOMAIN, SERVICE_PULL_DEVICES, poll_devices_update)

    def force_update(call):
        """Force all devices to pull data."""
        dispatcher_send(hass, SIGNAL_UPDATE_ENTITY)

    hass.services.register(DOMAIN, SERVICE_FORCE_UPDATE, force_update)

    return True


class TuyaDevice(Entity):
    """Tuya base device."""

    def __init__(self, tuya):
        """Init Tuya devices."""
        self.tuya = tuya

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        dev_id = self.tuya.object_id()
        self.hass.data[DOMAIN]['entities'][dev_id] = self.entity_id
        async_dispatcher_connect(
            self.hass, SIGNAL_DELETE_ENTITY, self._delete_callback)
        async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_ENTITY, self._update_callback)

    @property
    def object_id(self):
        """Return Tuya device id."""
        return self.tuya.object_id()

    @property
    def unique_id(self):
        """Return a unique ID."""
        return 'tuya.{}'.format(self.tuya.object_id())

    @property
    def name(self):
        """Return Tuya device name."""
        return self.tuya.name()

    @property
    def available(self):
        """Return if the device is available."""
        return self.tuya.available()

    def update(self):
        """Refresh Tuya device data."""
        self.tuya.update()

    @callback
    def _delete_callback(self, dev_id):
        """Remove this entity."""
        if dev_id == self.object_id:
            self.hass.async_create_task(self.async_remove())

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)
