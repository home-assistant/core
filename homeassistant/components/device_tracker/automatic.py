"""
Support for the Automatic platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.automatic/
"""
from datetime import timedelta
import logging
import re
import requests

import voluptuous as vol

from homeassistant.components.device_tracker import (PLATFORM_SCHEMA,
                                                     ATTR_ATTRIBUTES)
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_utc_time_change
from homeassistant.util import datetime as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_CLIENT_ID = 'client_id'
CONF_SECRET = 'secret'
CONF_DEVICES = 'devices'

SCOPE = 'scope:location scope:vehicle:profile scope:user:profile scope:trip'

ATTR_ACCESS_TOKEN = 'access_token'
ATTR_EXPIRES_IN = 'expires_in'
ATTR_RESULTS = 'results'
ATTR_VEHICLE = 'vehicle'
ATTR_ENDED_AT = 'ended_at'
ATTR_END_LOCATION = 'end_location'

URL_AUTHORIZE = 'https://accounts.automatic.com/oauth/access_token/'
URL_VEHICLES = 'https://api.automatic.com/vehicle/'
URL_TRIPS = 'https://api.automatic.com/trip/'

_VEHICLE_ID_REGEX = re.compile(
    (URL_VEHICLES + '(.*)?[/]$').replace('/', r'\/'))

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CLIENT_ID): cv.string,
    vol.Required(CONF_SECRET): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_DEVICES): vol.All(cv.ensure_list, [cv.string])
})


def setup_scanner(hass, config: dict, see):
    """Validate the configuration and return an Automatic scanner."""
    try:
        AutomaticDeviceScanner(hass, config, see)
    except requests.HTTPError as err:
        _LOGGER.error(str(err))
        return False

    return True


# pylint: disable=too-many-instance-attributes
# pylint: disable=too-few-public-methods
class AutomaticDeviceScanner(object):
    """A class representing an Automatic device."""

    def __init__(self, hass, config: dict, see) -> None:
        """Initialize the automatic device scanner."""
        self.hass = hass
        self._devices = config.get(CONF_DEVICES, None)
        self._access_token_payload = {
            'username': config.get(CONF_USERNAME),
            'password': config.get(CONF_PASSWORD),
            'client_id': config.get(CONF_CLIENT_ID),
            'client_secret': config.get(CONF_SECRET),
            'grant_type': 'password',
            'scope': SCOPE
        }
        self._headers = None
        self._token_expires = dt_util.now()
        self.last_results = {}
        self.last_trips = {}
        self.see = see

        self._update_info()

        track_utc_time_change(self.hass, self._update_info,
                              second=range(0, 60, 30))

    def _update_headers(self):
        """Get the access token from automatic."""
        if self._headers is None or self._token_expires <= dt_util.now():
            resp = requests.post(
                URL_AUTHORIZE,
                data=self._access_token_payload)

            resp.raise_for_status()

            json = resp.json()

            access_token = json[ATTR_ACCESS_TOKEN]
            self._token_expires = dt_util.now() + timedelta(
                seconds=json[ATTR_EXPIRES_IN])
            self._headers = {
                'Authorization': 'Bearer {}'.format(access_token)
            }

    def _update_info(self, now=None) -> None:
        """Update the device info."""
        _LOGGER.debug('Updating devices %s', now)
        self._update_headers()

        response = requests.get(URL_VEHICLES, headers=self._headers)

        response.raise_for_status()

        self.last_results = [item for item in response.json()[ATTR_RESULTS]
                             if self._devices is None or item[
                                 'display_name'] in self._devices]

        response = requests.get(URL_TRIPS, headers=self._headers)

        if response.status_code == 200:
            for trip in response.json()[ATTR_RESULTS]:
                vehicle_id = _VEHICLE_ID_REGEX.match(
                    trip[ATTR_VEHICLE]).group(1)
                if vehicle_id not in self.last_trips:
                    self.last_trips[vehicle_id] = trip
                elif self.last_trips[vehicle_id][ATTR_ENDED_AT] < trip[
                        ATTR_ENDED_AT]:
                    self.last_trips[vehicle_id] = trip

        for vehicle in self.last_results:
            dev_id = vehicle.get('id')
            host_name = vehicle.get('display_name')

            attrs = {
                'fuel_level': vehicle.get('fuel_level_percent')
            }

            kwargs = {
                'dev_id': dev_id,
                'host_name': host_name,
                'mac': dev_id,
                ATTR_ATTRIBUTES: attrs
            }

            if dev_id in self.last_trips:
                end_location = self.last_trips[dev_id][ATTR_END_LOCATION]
                kwargs['gps'] = (end_location['lat'], end_location['lon'])
                kwargs['gps_accuracy'] = end_location['accuracy_m']

            self.see(**kwargs)
