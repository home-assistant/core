"""
Support for information from HP ILO sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.sensor.hp_ilo/
"""
import logging
from datetime import timedelta

import voluptuous as vol
import jsonpath_rw

from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD, CONF_NAME,
    CONF_MONITORED_VARIABLES, CONF_PATH, CONF_SENSOR_TYPE,
    CONF_UNIT_OF_MEASUREMENT, STATE_ON, STATE_OFF)
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['python-hpilo==3.9', 'jsonpath_rw==1.4.0']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'HP ILO'
DEFAULT_PORT = 443
DEFAULT_SENSOR_PATH = '$'
DEFAULT_UNIT_OF_MEASUREMENT = None

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=300)

SENSOR_TYPES = {
    'server_name': ['Server Name', 'get_server_name'],
    'server_fqdn': ['Server FQDN', 'get_server_fqdn'],
    'server_host_data': ['Server Host Data', 'get_host_data'],
    'server_oa_info': ['Server Onboard Administrator Info', 'get_oa_info'],
    'server_power_status': ['Server Power state', 'get_host_power_status'],
    'server_power_readings': ['Server Power readings', 'get_power_readings'],
    'server_power_on_time': ['Server Power On time',
                             'get_server_power_on_time'],
    'server_asset_tag': ['Server Asset Tag', 'get_asset_tag'],
    'server_uid_status': ['Server UID light', 'get_uid_status'],
    'server_health': ['Server Health', 'get_embedded_health'],
    'network_settings': ['Network Settings', 'get_network_settings']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_MONITORED_VARIABLES, default=[]):
        vol.All(cv.ensure_list, [vol.Schema({
            vol.Required(CONF_NAME): cv.string,
            vol.Required(CONF_SENSOR_TYPE):
                vol.All(cv.string, vol.In(SENSOR_TYPES)),
            vol.Optional(CONF_UNIT_OF_MEASUREMENT,
                         default=DEFAULT_UNIT_OF_MEASUREMENT): cv.string,
            vol.Optional(CONF_PATH, default=DEFAULT_SENSOR_PATH): cv.string
        })]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the HP ILO sensor."""
    hostname = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    login = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    monitored_variables = config.get(CONF_MONITORED_VARIABLES)

    # Create a data fetcher to support all of the configured sensors. Then make
    # the first call to init the data and confirm we can connect.
    try:
        hp_ilo_data = HpIloData(hostname, port, login, password)
    except ValueError as error:
        _LOGGER.error(error)
        return False

    # Initialize and add all of the sensors.
    devices = []
    for monitored_variable in monitored_variables:
        new_device = HpIloSensor(
            hp_ilo_data=hp_ilo_data,
            sensor_name='{} {}'.format(
                config.get(CONF_NAME), monitored_variable[CONF_NAME]),
            sensor_type=monitored_variable[CONF_SENSOR_TYPE],
            sensor_path=monitored_variable[CONF_PATH],
            unit_of_measurement=monitored_variable[CONF_UNIT_OF_MEASUREMENT])
        devices.append(new_device)

    add_devices(devices)


class HpIloSensor(Entity):
    """Representation of a HP ILO sensor."""

    def __init__(self, hp_ilo_data, sensor_type, sensor_name, sensor_path,
                 unit_of_measurement):
        """Initialize the sensor."""
        self._name = sensor_name
        self._unit_of_measurement = unit_of_measurement
        self._ilo_function = SENSOR_TYPES[sensor_type][1]
        self.sensor_path = sensor_path
        self.hp_ilo_data = hp_ilo_data

        self._state = None
        self._data = None

        self.update()

        _LOGGER.debug("Created HP ILO sensor %r", self)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._data

    def update(self):
        """Get the latest data from HP ILO and updates the states."""
        # Call the API for new data. Each sensor will re-trigger this
        # same exact call, but that's fine. Results should be cached for
        # a short period of time to prevent hitting API limits.
        self.hp_ilo_data.update()
        ilo_data = getattr(self.hp_ilo_data.data, self._ilo_function)()

        if self.sensor_path is not DEFAULT_SENSOR_PATH:
            try:
                ilo_data = jsonpath_rw.parse(self.sensor_path).find(
                    ilo_data)[0].value
            except IndexError:
                _LOGGER.warning(
                    "No result found in ILO data for jsonpath '%s'",
                    self.sensor_path)

        # If the data received is an integer or string, store it as
        # the sensor state, otherwise store the data in the sensor attributes
        if isinstance(ilo_data, (str, bytes)):
            states = [STATE_ON, STATE_OFF]
            try:
                index_element = states.index(str(ilo_data).lower())
                self._state = states[index_element]
            except ValueError:
                self._state = ilo_data
        elif isinstance(ilo_data, (int, float)):
            self._state = ilo_data
        else:
            self._data = {'ilo_data': ilo_data}


class HpIloData(object):
    """Gets the latest data from HP ILO."""

    def __init__(self, host, port, login, password):
        """Initialize the data object."""
        self._host = host
        self._port = port
        self._login = login
        self._password = password

        self.data = None

        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from HP ILO."""
        import hpilo

        try:
            self.data = hpilo.Ilo(
                hostname=self._host, login=self._login,
                password=self._password, port=self._port)
        except (hpilo.IloError, hpilo.IloCommunicationError,
                hpilo.IloLoginFailed) as error:
            raise ValueError("Unable to init HP ILO, %s", error)
