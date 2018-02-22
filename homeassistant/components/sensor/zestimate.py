"""
Support for zestimate data from zillow.com.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.zestimate/
"""
import logging
from datetime import timedelta

import voluptuous as vol
import requests

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_API_KEY,
                                 CONF_NAME, STATE_UNKNOWN, ATTR_ATTRIBUTION)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['xmltodict==0.11.0']

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'http://www.zillow.com/webservice/GetZestimate.htm'

CONF_ZPID = 'zpid'
CONF_ATTRIBUTION = "Data provided by Zillow.com"

DEFAULT_NAME = 'Zestimate'
NAME = 'zestimate'
ZESTIMATE = '{}:{}'.format(DEFAULT_NAME, NAME)

ICON = 'mdi:home-variant'

ATTR_LOCATION = 'location'
ATTR_UPDATE = 'update'
ATTR_AMOUNT = 'amount'
ATTR_CHANGE = 'amount_change_30days'
ATTR_CURRENCY = 'amount_currency'
ATTR_LAST_UPDATED = 'amount_last_updated'
ATTR_VAL_HIGH = 'valuation_range_high'
ATTR_VAL_LOW = 'valuation_range_low'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_ZPID): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Zestimate sensor."""
    import xmltodict

    name = config.get(CONF_NAME)
    properties = config[CONF_ZPID]
    params = {'zws-id': config[CONF_API_KEY]}

    sensors = []
    for zpid in properties:
        params['zpid'] = zpid
        try:
            response = requests.get(_RESOURCE, params=params, timeout=5)
            data = response.content.decode('utf-8')
            data_dict = xmltodict.parse(data).get(ZESTIMATE)
            error_code = int(data_dict['message']['code'])
            if error_code != 0:
                _LOGGER.error('The API returned: %s',
                              data_dict['message']['text'])
                return False
        except requests.exceptions.ConnectionError:
            _LOGGER.error('The URL is not accessible')
            return False

        data = ZestimateData(params)
        sensors.append(ZestimateDataSensor(name, data))
    add_devices(sensors, True)


class ZestimateDataSensor(Entity):
    """Implementation of a Zestimate sensor."""

    def __init__(self, name, data):
        """Initialize the sensor."""
        self.data = data
        self._name = name
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        try:
            return round(float(self._state), 1)
        except ValueError:
            return STATE_UNKNOWN

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = {}
        if self.data.measurings is not None:
            if ATTR_AMOUNT in self.data.measurings:
                data = self.data.measurings
                attributes[ATTR_AMOUNT] = data[ATTR_AMOUNT]
                attributes[ATTR_CURRENCY] = data[ATTR_CURRENCY]
                attributes[ATTR_LAST_UPDATED] = data[ATTR_LAST_UPDATED]
                attributes[ATTR_CHANGE] = data[ATTR_CHANGE]
                attributes[ATTR_VAL_HIGH] = data[ATTR_VAL_HIGH]
                attributes[ATTR_VAL_LOW] = data[ATTR_VAL_LOW]

            attributes[ATTR_LOCATION] = self.data.address
            attributes[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
            return attributes

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data and update the states."""
        self.data.update()
        if self.data.measurings is not None:
            if ATTR_LAST_UPDATED not in self.data.measurings:
                self._state = STATE_UNKNOWN
            else:
                self._state = self.data.measurings[ATTR_AMOUNT]


class ZestimateData(object):
    """The Class for handling data retrieval."""

    def __init__(self, params):
        """Initialize the data object."""
        self.params = params
        self.address = None
        self.measurings = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from hydrodata.ch."""
        import xmltodict

        details = {}
        try:
            response = requests.get(_RESOURCE, params=self.params, timeout=5)
        except requests.exceptions.ConnectionError:
            _LOGGER.error('Unable to retrieve data from %s', _RESOURCE)

        try:
            decoded = response.content.decode('utf-8')
            to_dict = xmltodict.parse(decoded)
            response = to_dict.get(ZESTIMATE)['response']
            data = response[NAME]
            details[ATTR_AMOUNT] = data['amount']['#text']
            details[ATTR_CURRENCY] = data['amount']['@currency']
            details[ATTR_LAST_UPDATED] = data['last-updated']
            details[ATTR_CHANGE] = int(data['valueChange']['#text'])
            details[ATTR_VAL_HIGH] = int(data['valuationRange']['high']['#text'])
            details[ATTR_VAL_LOW] = int(data['valuationRange']['low']['#text'])

            self.address = response['address']['street']
            self.measurings = details
        except AttributeError:
            self.measurings = None
