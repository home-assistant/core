"""
Support for Efergy sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.efergy/
"""
import logging
import voluptuous as vol

from requests import RequestException, get

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'https://engage.efergy.com/mobile_proxy/'

CONF_APPTOKEN = 'app_token'
CONF_UTC_OFFSET = 'utc_offset'
CONF_MONITORED_VARIABLES = 'monitored_variables'
CONF_SENSOR_TYPE = 'type'

CONF_CURRENCY = 'currency'
CONF_PERIOD = 'period'

CONF_INSTANT = 'instant_readings'
CONF_BUDGET = 'budget'
CONF_COST = 'cost'

SENSOR_TYPES = {
    CONF_INSTANT: ['Energy Usage', 'kW'],
    CONF_BUDGET: ['Energy Budget', None],
    CONF_COST: ['Energy Cost', None],
}

TYPES_SCHEMA = vol.In(
    [CONF_INSTANT, CONF_BUDGET, CONF_COST])

SENSORS_SCHEMA = vol.Schema({
    vol.Required(CONF_SENSOR_TYPE): TYPES_SCHEMA,
    vol.Optional(CONF_CURRENCY, default=''): cv.string,
    vol.Optional(CONF_PERIOD, default='year'): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_APPTOKEN): cv.string,
    vol.Optional(CONF_UTC_OFFSET): cv.string,
    vol.Required(CONF_MONITORED_VARIABLES): [SENSORS_SCHEMA]
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Efergy sensor."""
    app_token = config.get(CONF_APPTOKEN)
    utc_offset = str(config.get(CONF_UTC_OFFSET))
    dev = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        dev.append(EfergySensor(
            variable[CONF_SENSOR_TYPE], app_token, utc_offset,
            variable[CONF_PERIOD], variable[CONF_CURRENCY]))

    add_devices(dev)


# pylint: disable=too-many-instance-attributes
class EfergySensor(Entity):
    """Implementation of an Efergy sensor."""

    # pylint: disable=too-many-arguments
    def __init__(self, sensor_type, app_token, utc_offset, period, currency):
        """Initialize the sensor."""
        self._name = SENSOR_TYPES[sensor_type][0]
        self.type = sensor_type
        self.app_token = app_token
        self.utc_offset = utc_offset
        self._state = None
        self.period = period
        self.currency = currency
        if self.type == 'cost':
            self._unit_of_measurement = self.currency + '/' + self.period
        else:
            self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Get the Efergy monitor data from the web service."""
        try:
            if self.type == 'instant_readings':
                url_string = _RESOURCE + 'getInstant?token=' + self.app_token
                response = get(url_string)
                self._state = response.json()['reading'] / 1000
            elif self.type == 'budget':
                url_string = _RESOURCE + 'getBudget?token=' + self.app_token
                response = get(url_string)
                self._state = response.json()['status']
            elif self.type == 'cost':
                url_string = _RESOURCE + 'getCost?token=' + self.app_token \
                    + '&offset=' + self.utc_offset + '&period=' \
                    + self.period
                response = get(url_string)
                self._state = response.json()['sum']
            else:
                self._state = 'Unknown'
        except (RequestException, ValueError, KeyError):
            _LOGGER.warning('Could not update status for %s', self.name)
