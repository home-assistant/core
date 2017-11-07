"""
Support for Canary.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/canary/
"""
import logging
from datetime import timedelta

import voluptuous as vol
from requests import ConnectTimeout, HTTPError

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, TEMP_CELSIUS, \
    TEMP_FAHRENHEIT, CONF_TIMEOUT
from homeassistant.helpers import discovery
from homeassistant.util import Throttle

REQUIREMENTS = ['py-canary==0.1.2']

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_ID = 'canary_notification'
NOTIFICATION_TITLE = 'Canary Setup'

DOMAIN = 'canary'
DATA_CANARY = 'canary'
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)
DEFAULT_TIMEOUT = 15

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Canary component."""
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    timeout = conf.get(CONF_TIMEOUT)

    try:
        hass.data[DATA_CANARY] = CanaryData(username, password, timeout)
    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Canary service: %s", str(ex))
        hass.components.persistent_notification.create(
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    discovery.load_platform(hass, 'sensor', DOMAIN, {}, config)
    discovery.load_platform(hass, 'camera', DOMAIN, {}, config)

    return True


class CanaryData(object):
    """Get the latest data and update the states."""

    def __init__(self, username, password, timeout):
        """Init the Canary data object."""
        from canary.api import Api
        self._api = Api(username, password, timeout)
        self._api.login()

        self._locations_by_id = {}
        self._devices_by_id = {}
        self._readings_by_device_id = {}
        self._entries_by_location_id = {}

        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from py-canary."""
        self._me = self._api.get_me()

        for location in self._api.get_locations():
            location_id = location.location_id

            self._locations_by_id[location_id] = location
            self._entries_by_location_id[location_id] = self._api.get_entries(
                location_id)

            for device in location.devices:
                if device.is_online:
                    self._devices_by_id[device.device_id] = device
                    self._readings_by_device_id[
                        device.device_id] = self._api.get_readings(device)

    @property
    def locations(self):
        """Return a list of locations."""
        return self._locations_by_id.values()

    @property
    def devices(self):
        """Return a list of devices."""
        return self._devices_by_id.values()

    @property
    def temperature_scale(self):
        """Return temperature scale."""
        if self._me.is_celsius:
            return TEMP_CELSIUS
        return TEMP_FAHRENHEIT

    def get_motion_entries(self, location_id):
        """Return a list of motion entries based on location_id."""
        if location_id not in self._entries_by_location_id:
            return []

        return self._entries_by_location_id[location_id]

    def get_location(self, location_id):
        """Return a location based on location_id."""
        if location_id not in self._locations_by_id:
            return []

        return self._locations_by_id[location_id]

    def get_readings(self, device_id):
        """Return a list of readings based on device_id."""
        return self._readings_by_device_id[device_id]
