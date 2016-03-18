"""
Support for Efergy sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.efergy/
"""
import logging

from requests import RequestException, get

from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'https://engage.efergy.com/mobile_proxy/'
SENSOR_TYPES = {
    'instant_readings': ['Energy Usage', 'kW'],
    'budget': ['Energy Budget', None],
    'cost': ['Energy Cost', None],
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Efergy sensor."""
    app_token = config.get("app_token")
    if not app_token:
        _LOGGER.error(
            "Configuration Error"
            "Please make sure you have configured your app token")
        return None
    utc_offset = str(config.get("utc_offset"))
    dev = []
    for variable in config['monitored_variables']:
        if 'period' not in variable:
            variable['period'] = ''
        if 'currency' not in variable:
            variable['currency'] = ''
        if variable['type'] not in SENSOR_TYPES:
            _LOGGER.error('Sensor type: "%s" does not exist', variable)
        else:
            dev.append(EfergySensor(variable['type'], app_token, utc_offset,
                                    variable['period'], variable['currency']))

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
