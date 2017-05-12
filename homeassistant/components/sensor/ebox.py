"""
Support for EBox.

Get data from 'My Usage Page' page: https://client.ebox.ca/myusage

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.ebox/
"""
import logging
from datetime import timedelta

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD,
    CONF_NAME, CONF_MONITORED_VARIABLES)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyebox==0.1.0']

_LOGGER = logging.getLogger(__name__)

GIGABITS = 'Gb'  # type: str
PRICE = 'CAD'  # type: str
DAYS = 'days'  # type: str
PERCENT = '%'  # type: str

DEFAULT_NAME = 'EBox'

REQUESTS_TIMEOUT = 15
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

SENSOR_TYPES = {
    'usage': ['Usage',
              PERCENT, 'mdi:percent'],
    'balance': ['Balance',
                PRICE, 'mdi:square-inc-cash'],
    'limit': ['Data limit',
              GIGABITS, 'mdi:download'],
    'days_left': ['Days left',
                  DAYS, 'mdi:calendar-today'],
    'before_offpeak_download': ['Download before offpeak',
                                GIGABITS, 'mdi:download'],
    'before_offpeak_upload': ['Upload before offpeak',
                              GIGABITS, 'mdi:upload'],
    'before_offpeak_total': ['Total before offpeak',
                             GIGABITS, 'mdi:download'],
    'offpeak_download': ['Offpeak download',
                         GIGABITS, 'mdi:download'],
    'offpeak_upload': ['Offpeak Upload',
                       GIGABITS, 'mdi:upload'],
    'offpeak_total': ['Offpeak Total',
                      GIGABITS, 'mdi:download'],
    'download': ['Download',
                 GIGABITS, 'mdi:download'],
    'upload': ['Upload',
               GIGABITS, 'mdi:upload'],
    'total': ['Total',
              GIGABITS, 'mdi:download'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_VARIABLES):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the EBox sensor."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    try:
        ebox_data = EBoxData(username, password)
        ebox_data.update()
    except requests.exceptions.HTTPError as error:
        _LOGGER.error("Failt login: %s", error)
        return False

    name = config.get(CONF_NAME)

    sensors = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        sensors.append(EBoxSensor(ebox_data, variable, name))

    add_devices(sensors, True)


class EBoxSensor(Entity):
    """Implementation of a EBox sensor."""

    def __init__(self, ebox_data, sensor_type, name):
        """Initialize the sensor."""
        self.client_name = name
        self.type = sensor_type
        self._name = SENSOR_TYPES[sensor_type][0]
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._icon = SENSOR_TYPES[sensor_type][2]
        self.ebox_data = ebox_data
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    def update(self):
        """Get the latest data from EBox and update the state."""
        self.ebox_data.update()
        if self.type in self.ebox_data.data:
            self._state = round(self.ebox_data.data[self.type], 2)


class EBoxData(object):
    """Get data from Ebox."""

    def __init__(self, username, password):
        """Initialize the data object."""
        from pyebox import EboxClient
        self.client = EboxClient(username, password, REQUESTS_TIMEOUT)
        self.data = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Ebox."""
        from pyebox.client import PyEboxError
        try:
            self.client.fetch_data()
        except PyEboxError as exp:
            _LOGGER.error("Error on receive last EBox data: %s", exp)
            return
        # Update data
        self.data = self.client.get_data()
