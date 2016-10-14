"""
Support for information from HP ILO sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.sensor.hp_ilo/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD, CONF_NAME,
    CONF_MONITORED_VARIABLES, STATE_ON, STATE_OFF)
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['python-hpilo==3.8']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'HP ILO'
DEFAULT_PORT = 443

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=300)

# Each sensor is defined as follows: 'Descriptive name', 'python-ilo function'
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
    vol.Optional(CONF_MONITORED_VARIABLES, default=['server_name']):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the HP ILO sensor."""
    hostname = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    login = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    monitored_variables = config.get(CONF_MONITORED_VARIABLES)
    name = config.get(CONF_NAME)

    # Create a data fetcher to support all of the configured sensors. Then make
    # the first call to init the data and confirm we can connect.
    try:
        hp_ilo_data = HpIloData(hostname, port, login, password)
    except ValueError as error:
        _LOGGER.error(error)
        return False

    # Initialize and add all of the sensors.
    devices = []
    for ilo_type in monitored_variables:
        new_device = HpIloSensor(hp_ilo_data=hp_ilo_data,
                                 sensor_type=SENSOR_TYPES.get(ilo_type),
                                 client_name=name)
        devices.append(new_device)

    add_devices(devices)


class HpIloSensor(Entity):
    """Representation a HP ILO sensor."""

    def __init__(self, hp_ilo_data, sensor_type, client_name):
        """Initialize the sensor."""
        self._name = '{} {}'.format(client_name, sensor_type[0])
        self._ilo_function = sensor_type[1]
        self.client_name = client_name
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
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return self._data

    def update(self):
        """Get the latest data from HP ILO and updates the states."""
        # Call the API for new data. Each sensor will re-trigger this
        # same exact call, but that's fine. Results should be cached for
        # a short period of time to prevent hitting API limits.
        self.hp_ilo_data.update()
        ilo_data = getattr(self.hp_ilo_data.data, self._ilo_function)()

        # Store the data received from the ILO API
        if isinstance(ilo_data, dict):
            self._data = ilo_data
        else:
            self._data = {'value': ilo_data}

        # If the data received is an integer or string, store it as
        # the sensor state
        if isinstance(ilo_data, (str, bytes)):
            states = [STATE_ON, STATE_OFF]
            try:
                index_element = states.index(str(ilo_data).lower())
                self._state = states[index_element]
            except ValueError:
                self._state = ilo_data
        elif isinstance(ilo_data, (int, float)):
            self._state = ilo_data


# pylint: disable=too-few-public-methods
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
            self.data = hpilo.Ilo(hostname=self._host,
                                  login=self._login,
                                  password=self._password,
                                  port=self._port)
        except (hpilo.IloError, hpilo.IloCommunicationError,
                hpilo.IloLoginFailed) as error:
            raise ValueError("Unable to init HP ILO, %s", error)
