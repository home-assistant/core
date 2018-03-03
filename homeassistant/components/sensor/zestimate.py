"""
Support for zestimate data from zillow.com.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.zestimate/
"""
from datetime import timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_API_KEY,
                                 CONF_NAME, ATTR_ATTRIBUTION)
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

ATTR_AMOUNT = 'amount'
ATTR_CHANGE = 'amount_change_30_days'
ATTR_CURRENCY = 'amount_currency'
ATTR_LAST_UPDATED = 'amount_last_updated'
ATTR_VAL_HI = 'valuation_range_high'
ATTR_VAL_LOW = 'valuation_range_low'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_ZPID): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Zestimate sensor."""
    name = config.get(CONF_NAME)
    properties = config[CONF_ZPID]
    params = {'zws-id': config[CONF_API_KEY]}

    sensors = []
    for zpid in properties:
        params['zpid'] = zpid
        sensors.append(ZestimateDataSensor(name, params))
    add_devices(sensors, True)


class ZestimateDataSensor(Entity):
    """Implementation of a Zestimate sensor."""

    def __init__(self, name, params):
        """Initialize the sensor."""
        self._name = name
        self.params = params
        self.data = None
        self.address = None
        self._state = None

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
            return None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = {}
        if self.data is not None:
            attributes = self.data
        attributes['address'] = self.address
        attributes[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        return attributes

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data and update the states."""
        import xmltodict
        try:
            response = requests.get(_RESOURCE, params=self.params, timeout=5)
            data = response.content.decode('utf-8')
            data_dict = xmltodict.parse(data).get(ZESTIMATE)
            error_code = int(data_dict['message']['code'])
            if error_code != 0:
                _LOGGER.error('The API returned: %s',
                              data_dict['message']['text'])
                return
        except requests.exceptions.ConnectionError:
            _LOGGER.error('Unable to retrieve data from %s', _RESOURCE)
            return
        data = data_dict['response'][NAME]
        details = {}
        details[ATTR_AMOUNT] = data['amount']['#text']
        details[ATTR_CURRENCY] = data['amount']['@currency']
        details[ATTR_LAST_UPDATED] = data['last-updated']
        details[ATTR_CHANGE] = int(data['valueChange']['#text'])
        details[ATTR_VAL_HI] = int(data['valuationRange']['high']['#text'])
        details[ATTR_VAL_LOW] = int(data['valuationRange']['low']['#text'])
        self.address = data_dict['response']['address']['street']
        self.data = details
        if self.data is not None:
            self._state = self.data[ATTR_AMOUNT]
        else:
            self._state = None
            _LOGGER.error('Unable to parase Zestimate data from response')
