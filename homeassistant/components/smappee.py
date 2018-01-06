"""
Support for Digital Ocean.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/smappee/
"""
import logging
from datetime import datetime, timedelta

import voluptuous as vol
from requests.exceptions import RequestException
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, CONF_NAME, CONF_HOST
)
from homeassistant.util import Throttle
from homeassistant.helpers.discovery import load_platform
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['smappy==0.2.13']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Smappee'
DEFAULT_HOST_PASSWORD = 'admin'

CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'
CONF_HOST_PASSWORD = 'host_password'

DOMAIN = 'smappee'
DATA_SMAPPEE = 'SMAPPEE'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_HOST_PASSWORD, default=DEFAULT_HOST_PASSWORD):
            cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Smapee component."""
    client_id = config.get(DOMAIN).get(CONF_CLIENT_ID)
    client_secret = config.get(DOMAIN).get(CONF_CLIENT_SECRET)
    username = config.get(DOMAIN).get(CONF_USERNAME)
    password = config.get(DOMAIN).get(CONF_PASSWORD)
    host = config.get(DOMAIN).get(CONF_HOST)
    host_password = config.get(DOMAIN).get(CONF_HOST_PASSWORD)

    try:
        smappee = Smappee(
            client_id, client_secret, username, password, host, host_password
        )
    except RequestException:
        _LOGGER.exception("Setup of Smappee component failed")
        smappee = None
        return False

    hass.data[DATA_SMAPPEE] = smappee

    load_platform(hass, 'switch', DOMAIN)
    load_platform(hass, 'sensor', DOMAIN)

    return True


class Smappee(object):
    """Stores data retrieved from Smappee sensor."""

    def __init__(self, client_id, client_secret, username,
                 password, host, host_password):
        """Initialize the data."""
        import smappy

        try:
            self._smappy = smappy.Smappee(client_id, client_secret)
            self._smappy.authenticate(username, password)
        except RequestException:
            self._smappy = None
            _LOGGER.exception("Smappee server authentication failed")

        try:
            self._localsmappy = smappy.LocalSmappee(host)
            self._localsmappy.logon(host_password)
        except RequestException:
            self._localsmappy = None
            _LOGGER.exception("Local Smappee device authentication failed")

        self.locations = {}
        self.info = {}

        if self._smappy is not None:
            self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update data from Smappee API."""
        service_locations = self._smappy.get_service_locations() \
            .get('serviceLocations')
        for location in service_locations:
            location_id = location.get('serviceLocationId')
            if location_id is not None:
                self.locations[location_id] = location.get('name')
                self.info[location_id] = self._smappy \
                    .get_service_location_info(location_id)

    def get_consumption(self, location_id, aggregation, delta):
        """Update data from Smappee."""
        # Start & End accept epoch (in milliseconds),
        #   datetime and pandas timestamps
        # Aggregation:
        # 1 = 5 min values (only available for the last 14 days),
        # 2 = hourly values,
        # 3 = daily values,
        # 4 = monthly values,
        # 5 = quarterly values
        end = datetime.utcnow()
        start = end - timedelta(minutes=delta)
        return self._smappy.get_consumption(location_id, start,
                                            end, aggregation)

    def get_sensor_consumption(self, location_id, sensor_id):
        """Update data from Smappee."""
        # Start & End accept epoch (in milliseconds),
        #   datetime and pandas timestamps
        # Aggregation:
        # 1 = 5 min values (only available for the last 14 days),
        # 2 = hourly values,
        # 3 = daily values,
        # 4 = monthly values,
        # 5 = quarterly values
        start = datetime.utcnow() - timedelta(minutes=30)
        end = datetime.utcnow()
        return self._smappy.get_sensor_consumption(location_id, sensor_id,
                                                   start, end, 1)

    def actuator_on(self, location_id, actuator_id, duration=None):
        """Turn on actuator."""
        # Duration = 300,900,1800,3600
        #  or any other value for an undetermined period of time.
        self._smappy.actuator_on(location_id, actuator_id, duration)

    def actuator_off(self, location_id, actuator_id, duration=None):
        """Turn off actuator."""
        # Duration = 300,900,1800,3600
        #  or any other value for an undetermined period of time.
        self._smappy.actuator_off(location_id, actuator_id, duration)

    def active_power(self):
        """Get sum of all instantanious active power values from local hub."""
        if self._localsmappy:
            return self._localsmappy.active_power()
        return False

    def report_instantaneous_values(self):
        """ReportInstantaneousValues."""
        if self._localsmappy:
            return self._localsmappy.report_instantaneous_values()
        return False

    def load_instantaneous(self):
        """LoadInstantaneous."""
        if self._localsmappy:
            return self._localsmappy.load_instantaneous()
        return False
