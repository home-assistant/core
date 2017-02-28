import logging

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.lock import LockDevice
from homeassistant.components.lock import PLATFORM_SCHEMA
from homeassistant.const import CONF_ACCESS_TOKEN, SERVICE_LOCK, \
    SERVICE_UNLOCK, CONF_ID

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'lockitron'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ACCESS_TOKEN): cv.string,
    vol.Required(CONF_ID): cv.string
})
BASE_URL = 'https://api.lockitron.com'
API_STATE_URL = BASE_URL + '/v2/locks/{}?access_token={}'
API_ACTION_URL = BASE_URL + '/v2/locks/{}?access_token={}&state={}'


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    access_token = config.get(CONF_ACCESS_TOKEN)
    device_id = config.get(CONF_ID)
    response = requests.get(API_STATE_URL.format(device_id, access_token))
    if response.status_code == 200:
        add_devices([Lockitron(response.json()['state'], access_token,
                               device_id)])
    else:
        _LOGGER.error('Error retrieving lock status during init: %s',
                      response.text)


class Lockitron(LockDevice):
    def __init__(self, state, access_token, device_id):
        """Initialize the lock."""
        self._state = state
        self.access_token = access_token
        self.device_id = device_id

    @property
    def should_poll(self):
        return True

    @property
    def name(self):
        return DOMAIN

    @property
    def is_locked(self):
        return self._state == SERVICE_LOCK

    def lock(self, **kwargs):
        """Lock the device."""
        self._state = self.do_change_request(SERVICE_LOCK)
        self.update_ha_state()

    def unlock(self, **kwargs):
        """Unlock the device."""
        self._state = self.do_change_request(SERVICE_UNLOCK)
        self.update_ha_state()

    def async_update(self):
        response = requests.get(API_STATE_URL.format(self.device_id, self.access_token))
        if response.status_code == 200:
            self._state = response.json()['state']
        else:
            _LOGGER.error('Error retrieving lock status: %s', response.text)

    def do_change_request(self, requested_state):
        response = requests.put(API_ACTION_URL.format(self.device_id,
                                                      self.access_token, requested_state))
        if response.status_code == 200:
            return response.json()['state']
        else:
            _LOGGER.error('Error setting lock state: %s\n%s',
                          requested_state, response.text)
            return self._state
