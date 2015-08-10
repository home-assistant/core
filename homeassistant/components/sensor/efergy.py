"""
homeassistant.components.sensor.efergy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Monitors home energy use as measured by an efergy engage hub using its
(unofficial, undocumented) API.

Configuration:

To use the efergy sensor you will need to add something like the following
to your config/configuration.yaml

sensor:
  platform: efergy
  app_token: APP_TOKEN
  utc_offset: UTC_OFFSET
  monitored_variables:
    - type: instant_readings
    - type: budget
    - type: cost
      period: day
      currency: $

Variables:

api_key
*Required
To get a new App Token, log in to your efergy account, go
to the Settings page, click on App tokens, and click "Add token".

utc_offset
*Required for some variables
Some variables (currently only the daily_cost) require that the
negative number of minutes your timezone is ahead/behind UTC time.

monitored_variables
*Required
An array specifying the variables to monitor.

period
*Optional
Some variables take a period argument. Valid options are "day", "week",
"month", and "year".

currency
*Optional
This is used to display the cost/period as the unit when monitoring the
cost. It should correspond to the actual currency used in your dashboard.
"""
import logging
from requests import get

from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'https://engage.efergy.com/mobile_proxy/'
SENSOR_TYPES = {
    'instant_readings': ['Energy Usage', 'kW'],
    'budget': ['Energy Budget', ''],
    'cost': ['Energy Cost', ''],
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the efergy sensor. """
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
    """ Implements an Efergy sensor. """

    # pylint: disable=too-many-arguments
    def __init__(self, sensor_type, app_token, utc_offset, period, currency):
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
        """ Returns the name. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def unit_of_measurement(self):
        """ Unit of measurement of this entity, if any. """
        return self._unit_of_measurement

    def update(self):
        """ Gets the efergy monitor data from the web service """
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
