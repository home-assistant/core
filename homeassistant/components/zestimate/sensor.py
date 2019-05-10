"""Support for zestimate data from zillow.com."""
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

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'http://www.zillow.com/webservice/GetZestimate.htm'

ATTRIBUTION = "Data provided by Zillow.com"

CONF_ZPID = 'zpid'

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


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Zestimate sensor."""
    name = config.get(CONF_NAME)
    properties = config[CONF_ZPID]

    sensors = []
    for zpid in properties:
        params = {'zws-id': config[CONF_API_KEY]}
        params['zpid'] = zpid
        sensors.append(ZestimateDataSensor(name, params))
    add_entities(sensors, True)


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
    def unique_id(self):
        """Return the ZPID."""
        return self.params['zpid']

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
        attributes[ATTR_ATTRIBUTION] = ATTRIBUTION
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
        if 'amount' in data and data['amount'] is not None:
            details[ATTR_AMOUNT] = data['amount']['#text']
            details[ATTR_CURRENCY] = data['amount']['@currency']
        if 'last-updated' in data and data['last-updated'] is not None:
            details[ATTR_LAST_UPDATED] = data['last-updated']
        if 'valueChange' in data and data['valueChange'] is not None:
            details[ATTR_CHANGE] = int(data['valueChange']['#text'])
        if 'valuationRange' in data and data['valuationRange'] is not None:
            details[ATTR_VAL_HI] = int(data['valuationRange']['high']['#text'])
            details[ATTR_VAL_LOW] = int(data['valuationRange']['low']['#text'])
        self.address = data_dict['response']['address']['street']
        self.data = details
        if self.data is not None:
            self._state = self.data[ATTR_AMOUNT]
        else:
            self._state = None
            _LOGGER.error('Unable to parase Zestimate data from response')
