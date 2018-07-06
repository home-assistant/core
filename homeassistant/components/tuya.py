"""
Support for Tuya Smart devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tuya/
"""
from datetime import timedelta
import logging
import time
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD)
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_interval

REQUIREMENTS = ['tuyapy==0.0.2']

_LOGGER = logging.getLogger(__name__)

CONF_COUNTRYCODE = 'countrycode'

DOMAIN = 'tuya'
DATA_TUYA = 'data_tuya'

SERVICE_FORCE_UPDATE = 'force_update'
SERVICE_PULL_DEVICES = 'pull_devices'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_COUNTRYCODE): cv.string
    })
}, extra=vol.ALLOW_EXTRA)

TUYA_COMPONENT = ['light']


def setup(hass, config):
    """Set up Tuya Component."""
    from tuyapy import TuyaApi

    tuya = TuyaApi()
    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    country_code = config[DOMAIN][CONF_COUNTRYCODE]

    hass.data[DATA_TUYA] = tuya

    tuya.init(username, password, country_code)

    hass.data[DOMAIN] = {
        'dev_ids': [],
        'entities': {}
    }

    devTypes = tuya.get_devTypes()
    for devType in devTypes:
        discovery.load_platform(hass, devType, DOMAIN, {}, config)

    def check_accesstoken(event_time):
        tuya = hass.data[DATA_TUYA]
        tuya.check_access_token()

    def poll_devices_update(event_time):
        print('poll devices update start ======')
        devices = tuya.poll_devices_update()
        devTypes = tuya.get_devTypes()

        if devices is None:
            return None
        """Add new discovered devices."""
        for devType in devTypes:
            discovery.load_platform(hass, devType, DOMAIN, {}, config)
        """Delete not exist devices."""
        newlist_ids = []
        for device in devices:
            newlist_ids.append(device.get('id'))
        for entity_list in hass.data[DOMAIN]['entities'].values():
            for entity in entity_list:
                if entity.object_id not in newlist_ids:
                    hass.add_job(entity.async_remove())
                    entity_list.remove(entity)
                    hass.data[DOMAIN]['dev_ids'].remove(entity.object_id)

    track_time_interval(hass, poll_devices_update, timedelta(minutes=2))

    hass.services.register(DOMAIN, SERVICE_PULL_DEVICES, poll_devices_update)

    def force_update(call):
        """Force all devices to pull data."""
        _LOGGER.info("Refreshing Device Data From Tuya")
        for entity_list in hass.data[DOMAIN]['entities'].values():
            for entity in entity_list:
                time.sleep(0.5)
                entity.schedule_update_ha_state(True)

    hass.services.register(DOMAIN, SERVICE_FORCE_UPDATE, force_update)

    return True


class TuyaDevice(Entity):
    """Tuya base device."""

    def __init__(self, tuya, hass):
        """Init Tuya devices."""
        self.hass = hass
        self.tuya = tuya

    @property
    def object_id(self):
        """Return Tuya device id."""
        return self.tuya.object_id()

    @property
    def name(self):
        """Return Tuya device name."""
        return self.tuya.name()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.tuya.state()

    @property
    def entity_picture(self):
        """Return the entity picture to use in the frontend, if any."""
        return self.tuya.iconurl()

    @property
    def available(self):
        """Return if the device is available."""
        return self.tuya.available()

    def update(self):
        """Refresh Tuya device data."""
        self.tuya.update()
