"""
Support for Smappee energy monitor.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/smappee/
"""
import logging
from datetime import datetime, timedelta
import re
import voluptuous as vol
from requests.exceptions import RequestException
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, CONF_HOST
)
from homeassistant.util import Throttle
from homeassistant.helpers.discovery import load_platform
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['smappy==0.2.15']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Smappee'
DEFAULT_HOST_PASSWORD = 'admin'

CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'
CONF_HOST_PASSWORD = 'host_password'

DOMAIN = 'smappee'
DATA_SMAPPEE = 'SMAPPEE'

_SENSOR_REGEX = re.compile(
    r'(?P<key>([A-Za-z]+))\=' +
    r'(?P<value>([0-9\.]+))')

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Inclusive(CONF_CLIENT_ID, 'Server credentials'): cv.string,
        vol.Inclusive(CONF_CLIENT_SECRET, 'Server credentials'): cv.string,
        vol.Inclusive(CONF_USERNAME, 'Server credentials'): cv.string,
        vol.Inclusive(CONF_PASSWORD, 'Server credentials'): cv.string,
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_HOST_PASSWORD, default=DEFAULT_HOST_PASSWORD):
            cv.string
    }),
}, extra=vol.ALLOW_EXTRA)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)


def setup(hass, config):
    """Set up the Smapee component."""
    client_id = config.get(DOMAIN).get(CONF_CLIENT_ID)
    client_secret = config.get(DOMAIN).get(CONF_CLIENT_SECRET)
    username = config.get(DOMAIN).get(CONF_USERNAME)
    password = config.get(DOMAIN).get(CONF_PASSWORD)
    host = config.get(DOMAIN).get(CONF_HOST)
    host_password = config.get(DOMAIN).get(CONF_HOST_PASSWORD)

    smappee = Smappee(client_id, client_secret, username,
                      password, host, host_password)

    if not smappee.is_local_active and not smappee.is_remote_active:
        _LOGGER.error("Neither Smappee server or local component enabled.")
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

        self._remote_active = False
        self._local_active = False
        if client_id is not None:
            try:
                self._smappy = smappy.Smappee(client_id, client_secret)
                self._smappy.authenticate(username, password)
                self._remote_active = True
            except RequestException as error:
                self._smappy = None
                _LOGGER.exception(
                    "Smappee server authentication failed (%s)",
                    error)
        else:
            _LOGGER.warning("Smappee server component init skipped.")

        if host is not None:
            try:
                self._localsmappy = smappy.LocalSmappee(host)
                self._localsmappy.logon(host_password)
                self._local_active = True
            except RequestException as error:
                self._localsmappy = None
                _LOGGER.exception(
                    "Local Smappee device authentication failed (%s)",
                    error)
        else:
            _LOGGER.warning("Smappee local component init skipped.")

        self.locations = {}
        self.info = {}
        self.consumption = {}
        self.sensor_consumption = {}
        self.instantaneous = {}

        if self._remote_active or self._local_active:
            self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update data from Smappee API."""
        if self.is_remote_active:
            service_locations = self._smappy.get_service_locations() \
                .get('serviceLocations')
            for location in service_locations:
                location_id = location.get('serviceLocationId')
                if location_id is not None:
                    self.sensor_consumption[location_id] = {}
                    self.locations[location_id] = location.get('name')
                    self.info[location_id] = self._smappy \
                        .get_service_location_info(location_id)
                    _LOGGER.debug("Remote info %s %s",
                                  self.locations, self.info[location_id])

                    for sensors in self.info[location_id].get('sensors'):
                        sensor_id = sensors.get('id')
                        self.sensor_consumption[location_id]\
                            .update({sensor_id: self.get_sensor_consumption(
                                location_id, sensor_id,
                                aggregation=3, delta=1440)})
                    _LOGGER.debug("Remote sensors %s %s",
                                  self.locations,
                                  self.sensor_consumption[location_id])

                    self.consumption[location_id] = self.get_consumption(
                        location_id, aggregation=3, delta=1440)
                    _LOGGER.debug("Remote consumption %s %s",
                                  self.locations,
                                  self.consumption[location_id])

        if self.is_local_active:
            self.local_devices = self.get_switches()
            _LOGGER.debug("Local switches %s", self.local_devices)

            self.instantaneous = self.load_instantaneous()
            _LOGGER.debug("Local values %s", self.instantaneous)

    @property
    def is_remote_active(self):
        """Return true if Smappe server is configured and working."""
        return self._remote_active

    @property
    def is_local_active(self):
        """Return true if Smappe local device is configured and working."""
        return self._local_active

    def get_switches(self):
        """Get switches from local Smappee."""
        if not self.is_local_active:
            return

        try:
            return self._localsmappy.load_command_control_config()
        except RequestException as error:
            _LOGGER.error(
                "Error getting switches from local Smappee. (%s)",
                error)

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
        if not self.is_remote_active:
            return

        end = datetime.utcnow()
        start = end - timedelta(minutes=delta)
        try:
            return self._smappy.get_consumption(location_id,
                                                start,
                                                end,
                                                aggregation)
        except RequestException as error:
            _LOGGER.error(
                "Error getting comsumption from Smappee cloud. (%s)",
                error)

    def get_sensor_consumption(self, location_id, sensor_id,
                               aggregation, delta):
        """Update data from Smappee."""
        # Start & End accept epoch (in milliseconds),
        #   datetime and pandas timestamps
        # Aggregation:
        # 1 = 5 min values (only available for the last 14 days),
        # 2 = hourly values,
        # 3 = daily values,
        # 4 = monthly values,
        # 5 = quarterly values
        if not self.is_remote_active:
            return

        end = datetime.utcnow()
        start = end - timedelta(minutes=delta)
        try:
            return self._smappy.get_sensor_consumption(location_id,
                                                       sensor_id,
                                                       start,
                                                       end, aggregation)
        except RequestException as error:
            _LOGGER.error(
                "Error getting comsumption from Smappee cloud. (%s)",
                error)

    def actuator_on(self, location_id, actuator_id,
                    is_remote_switch, duration=None):
        """Turn on actuator."""
        # Duration = 300,900,1800,3600
        #  or any other value for an undetermined period of time.
        #
        # The comport plugs have a tendency to ignore the on/off signal.
        # And because you can't read the status of a plug, it's more
        # reliable to execute the command twice.
        try:
            if is_remote_switch:
                self._smappy.actuator_on(location_id, actuator_id, duration)
                self._smappy.actuator_on(location_id, actuator_id, duration)
            else:
                self._localsmappy.on_command_control(actuator_id)
                self._localsmappy.on_command_control(actuator_id)
        except RequestException as error:
            _LOGGER.error(
                "Error turning actuator on. (%s)",
                error)
            return False

        return True

    def actuator_off(self, location_id, actuator_id,
                     is_remote_switch, duration=None):
        """Turn off actuator."""
        # Duration = 300,900,1800,3600
        #  or any other value for an undetermined period of time.
        #
        # The comport plugs have a tendency to ignore the on/off signal.
        # And because you can't read the status of a plug, it's more
        # reliable to execute the command twice.
        try:
            if is_remote_switch:
                self._smappy.actuator_off(location_id, actuator_id, duration)
                self._smappy.actuator_off(location_id, actuator_id, duration)
            else:
                self._localsmappy.off_command_control(actuator_id)
                self._localsmappy.off_command_control(actuator_id)
        except RequestException as error:
            _LOGGER.error(
                "Error turning actuator on. (%s)",
                error)
            return False

        return True

    def active_power(self):
        """Get sum of all instantaneous active power values from local hub."""
        if not self.is_local_active:
            return

        try:
            return self._localsmappy.active_power()
        except RequestException as error:
            _LOGGER.error(
                "Error getting data from Local Smappee unit. (%s)",
                error)

    def active_cosfi(self):
        """Get the average of all instantaneous cosfi values."""
        if not self.is_local_active:
            return

        try:
            return self._localsmappy.active_cosfi()
        except RequestException as error:
            _LOGGER.error(
                "Error getting data from Local Smappee unit. (%s)",
                error)

    def instantaneous_values(self):
        """ReportInstantaneousValues."""
        if not self.is_local_active:
            return

        report_instantaneous_values = \
            self._localsmappy.report_instantaneous_values()

        report_result = \
            report_instantaneous_values['report'].split('<BR>')
        properties = {}
        for lines in report_result:
            lines_result = lines.split(',')
            for prop in lines_result:
                match = _SENSOR_REGEX.search(prop)
                if match:
                    properties[match.group('key')] = \
                        match.group('value')
        _LOGGER.debug(properties)
        return properties

    def active_current(self):
        """Get current active Amps."""
        if not self.is_local_active:
            return

        properties = self.instantaneous_values()
        return float(properties['current'])

    def active_voltage(self):
        """Get current active Voltage."""
        if not self.is_local_active:
            return

        properties = self.instantaneous_values()
        return float(properties['voltage'])

    def load_instantaneous(self):
        """LoadInstantaneous."""
        if not self.is_local_active:
            return

        try:
            return self._localsmappy.load_instantaneous()
        except RequestException as error:
            _LOGGER.error(
                "Error getting data from Local Smappee unit. (%s)",
                error)
