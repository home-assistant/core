"""
Support for Blink4home cameras.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/blink4home/
"""
import asyncio
import logging
from datetime import timedelta
import json
import requests

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_NAME

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = 'Blink4Home camera support'
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)
CONF_NETWORK_ID = 'network_id'

DOMAIN = 'blink4home'
DATA_BLINK = 'blink4home'

API_URL = 'https://rest.prir.immedia-semi.com'
CLIENT_SPECIFIER = 'Home-Assistant | '
HEADERS = {'Content-Type': 'application/json'}
TOKEN_HEADER = 'TOKEN_AUTH'
UNAUTH_ACCESS = 'Unauthorized access'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NETWORK_ID, default=0): cv.positive_int,
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Setting up the platform."""
    blink_config = config.get(DOMAIN, {})

    username = blink_config.get(CONF_USERNAME)
    password = blink_config.get(CONF_PASSWORD)
    network = blink_config.get(CONF_NETWORK_ID)
    version = hass.config.as_dict()['version']

    def arm_blink(call):
        blink = hass.data[DATA_BLINK]
        blink.arm()

    def disarm_blink(call):
        blink = hass.data[DATA_BLINK]
        blink.disarm()

    blink = Blink4Home(username, password, version, network)
    # Store data
    hass.data[DATA_BLINK] = blink

    # Add service
    hass.services.async_register(DOMAIN, 'arm', arm_blink)
    hass.services.async_register(DOMAIN, 'disarm', disarm_blink)

    return blink.logged_in


class Blink4Home(object):
    """Blink4home api."""

    def __init__(self, username, password, version, network):
        """Init the Blink4Home api."""
        self._username = username
        self._password = password
        self._version = version
        self._api_key = ""
        self._network_id = ""
        self._network = network
        self._armed = False
        self._notifications = 0
        self._logged_in = False

        # Login
        self._login()

    @property
    def logged_in(self):
        """Return the name of the sensor."""
        return self._logged_in

    @property
    def notifications(self):
        """Return the amount of notifications."""
        return self._notifications

    @property
    def state(self):
        """Return the state."""
        return self._armed

    def _login(self, force=False):
        """Perform login."""
        if not self._api_key or force:
            self._api_key = ''

            url = (API_URL + '/login')
            data = {'password': self._password,
                    'client_specifier': CLIENT_SPECIFIER + str(self._version),
                    'email': self._username}
            _LOGGER.debug('Sending request with: %s',
                          json.dumps(data))

            response = requests.post(url,
                                     data=json.dumps(data),
                                     headers=HEADERS, timeout=10)

            if response.status_code == 200:
                _LOGGER.debug('Received login response: %s',
                              response.text)
                result = response.json()
                self._api_key = result['authtoken']['authtoken']
                _LOGGER.debug('Got api-key: %s',
                              self._api_key)

                networks = result['networks']
                found = False
                for key, value in networks.items():
                    _LOGGER.debug('Network: %s, value: %s',
                                  key, value)
                    # choose network from config or the first one (maybe the only one)
                    if not found and (self._network == 0 or str(self._network) == key):
                        self._network_id = key
                        found = True

                    if found:
                        break

                if found:
                    self._logged_in = True
                    self.update()

                _LOGGER.debug('Api key: %s',
                              json.dumps(self._api_key))
                _LOGGER.debug('Selected network: %s',
                              json.dumps(self._network_id))
            else:
                self._api_key = ''
                _LOGGER.debug('Received error response: %s',
                              response.status_code)
                _LOGGER.error('Error logging in to the Blink4Home platform. Received status was %s.',
                              response.status_code)

    def _do_post(self, url, data='', second_try=False):
        if not self._logged_in or not self._api_key:
            self._login(True)

        if not self._api_key:
            _LOGGER.error('Couldn\'t arm system. There was a problem with the login.')

        headers = HEADERS
        headers[TOKEN_HEADER] = self._api_key

        response = requests.post(url, data=data,
                                 headers=headers, timeout=10)

        if response.status_code == 401 and not second_try:
            _LOGGER.debug('Token not valid: %s',
                          response.status_code)
            self._login(True)
            self._do_post(url=url, data=data, second_try=True)
        else:
            _LOGGER.debug('Received error response on post: %s',
                          response.text)
            _LOGGER.error('Error with the Blink4Home platform. Received status was %s.',
                          response.status_code)

        return response

    def _do_get(self, url, second_try=False):
        if not self._logged_in or not self._api_key:
            self._login(True)

        if not self._api_key:
            _LOGGER.error('Couldn\'t arm system. There was a problem with the login.')

        headers = HEADERS
        headers[TOKEN_HEADER] = self._api_key

        response = requests.get(url, headers=headers,
                                timeout=10)

        if response.status_code == 401 and not second_try:
            _LOGGER.debug('Token not valid: %s',
                          response.status_code)
            self._login(True)
            self._do_get(url=url, second_try=True)
        else:
            _LOGGER.debug('Received error response on get: %s',
                          response.text)
            _LOGGER.error('Error with the Blink4Home platform. Received status was %s.',
                          response.status_code)

        return response

    def arm(self):
        """Arm the system."""
        _LOGGER.debug('Arming the system')
        response = self._do_post(API_URL + '/network/' + str(self._network_id) + '/arm')

        if response.status_code == 200:
            _LOGGER.debug('Received arm response: %s',
                          response.text)

            self.update()
        else:
            _LOGGER.debug('Received error response on update: %s',
                         response.text)
            _LOGGER.error('Error arming the Blink4Home platform. Received status was %s.',
                         response.status_code)

    def disarm(self, second_try=False):
        """Disarm the system."""
        _LOGGER.debug('Disarming the system')
        response = self._do_post(API_URL + '/network/' + str(self._network_id) + '/disarm')

        if response.status_code == 200:
            _LOGGER.debug('Received disarm response: %s',
                          response.text)

            self.update()
        else:
            _LOGGER.debug('Received error response on update: %s',
                         response.text)
            _LOGGER.error('Error disarming the Blink4Home platform. Received status was %s.',
                         response.status_code)

    def update(self, second_try=False):
        """Update the status."""
        _LOGGER.debug('Updating the system')
        response = self._do_get(API_URL + '/homescreen')

        if response.status_code == 200:
            _LOGGER.debug('Received update response: %s',
                          response.text)
            result = response.json()

            self._armed = result['network']['armed']
            self._notifications = result['network']['notifications']
        else:
            _LOGGER.debug('Received error response on update: %s',
                         response.text)
            _LOGGER.error('Error updating the Blink4Home sensor. Received status was %s.',
                         response.status_code)
