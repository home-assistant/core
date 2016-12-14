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

DEFAULT_NAME = 'Blink4Home'
ATTRIBUTION = 'Blink4Home camera support'
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)
CONF_NETWORK_ID = 'network_id'

DOMAIN = 'blink4home'
DATA_BLINK = 'blink4home'

API_URL = 'https://rest.prir.immedia-semi.com'
CLIENT_SPECIFIER = 'Home-Assistant | '
HEADERS = {'Content-Type': 'application/json'}
TOKEN_HEADER = 'TOKEN_AUTH'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
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
    name = blink_config.get(CONF_NAME)
    if name == '':
        name = DEFAULT_NAME
    network = blink_config.get(CONF_NETWORK_ID)
    version = hass.config.as_dict()['version']

    def arm_blink(call):
        blink = hass.data[DATA_BLINK]
        blink.arm()

    def disarm_blink(call):
        blink = hass.data[DATA_BLINK]
        blink.disarm()

    blink = Blink4Home(username, password, version, name, network)
    # Store data
    hass.data[DATA_BLINK] = blink

    # Add service
    hass.services.async_register(DOMAIN, 'arm', arm_blink)
    hass.services.async_register(DOMAIN, 'disarm', disarm_blink)

    return blink.logged_in


class Blink4Home(object):
    """Blink4home api."""

    def __init__(self, username, password, version, name, network):
        """Init the Blink4Home api."""
        self._username = username
        self._password = password
        self._version = version
        self._api_key = ""
        self._network_id = ""
        self._name = name
        self._network = network
        self._armed = False
        self._notifications = 0
        self._logged_in = False

        # Login
        self._login()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

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

    def _login(self):
        """Perform login."""
        if self._api_key == '':
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
                _LOGGER.debug('Received error response: %s',
                              response.status_code)
                _LOGGER.error('Error logging in to the Blink4Home platform. Received status was %s.',
                              response.status_code)

    def arm(self):
        """Arm the system."""
        _LOGGER.debug('Arming the system')
        if not self._logged_in:
            self._login()

        if self._api_key == '':
            _LOGGER.error('Couldn\'t arm system. There was a problem with the login.')

        url = (API_URL + '/network/' + str(self._network_id) + '/arm')
        headers = HEADERS
        headers[TOKEN_HEADER] = self._api_key

        response = requests.post(url, data='',
                                 headers=headers, timeout=10)

        if response.status_code == 200:
            _LOGGER.debug('Received arm response: %s',
                          response.text)
            self.update()
        else:
            _LOGGER.debug('Received error response on arm: %s',
                          response.status_code)
            _LOGGER.error('Error arming in to the Blink4Home platform. Received status was %s.',
                          response.status_code)

    def disarm(self):
        """Arm the system."""
        _LOGGER.debug('Disarming the system')
        if not self._logged_in:
            self._login()

        if self._api_key == '':
            _LOGGER.error('Couldn\'t disarm system. There was a problem with the login.')

        url = (API_URL + '/network/' + str(self._network_id) + '/disarm')
        headers = HEADERS
        headers[TOKEN_HEADER] = self._api_key

        response = requests.post(url, data='',
                                 headers=headers, timeout=10)

        if response.status_code == 200:
            _LOGGER.debug('Received disarm response: %s',
                          response.text)
            self.update()
        else:
            _LOGGER.debug('Received error response on disarm: %s',
                          response.status_code)
            _LOGGER.error('Error disarming in to the Blink4Home platform. Received status was %s.',
                          response.status_code)

    def update(self):
        """Update the status."""
        _LOGGER.debug('Update the system')
        if not self._logged_in:
            self._login()

        if self._api_key == '':
            _LOGGER.error('Couldn\'t update the system. There was a problem with the login.')

        url = (API_URL + '/homescreen')
        headers = HEADERS
        headers[TOKEN_HEADER] = self._api_key

        response = requests.get(url, headers=headers,
                                timeout=10)

        if response.status_code == 200:
            _LOGGER.debug('Received update response: %s',
                          response.text)
            result = response.json()
            self._armed = result['network']['armed']
            self._notifications = result['network']['notifications']
        else:
            _LOGGER.debug('Received error response on update: %s',
                          response.status_code)
            _LOGGER.error('Error updating in to the Blink4Home platform. Received status was %s.',
                          response.status_code)
