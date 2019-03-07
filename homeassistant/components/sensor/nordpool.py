"""Support for Nordpool electrical prices sensors."""
import logging

from datetime import datetime
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (ATTR_ATTRIBUTION,
                                 CONF_NAME,
                                 CONF_CURRENCY,
                                 CONF_REGION)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['nordpool==0.2']

_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:cash-usd'
ATTRIB = "For details, see https://nordpoolgroup.com/"

CURRENCY_FRACTION = {
    'DKK': 'Øre',
    'EUR': 'Cent',
    'NOK': 'Øre',
    'SEK': 'Øre'
}

VALID_REGION = ['DK1',
                'DK2',
                'EE',
                'FI',
                'LT',
                'LV',
                'Oslo',
                'Kr.sand',
                'Bergen',
                'Molde',
                'Tr.heim',
                'Tromsø',
                'SE1',
                'SE2',
                'SE3',
                'SE4',
                'SYS']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_CURRENCY): vol.All(cv.string, vol.In(CURRENCY_FRACTION)),
    vol.Required(CONF_REGION): vol.All(cv.string, vol.In(VALID_REGION)),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Nordpool sensor platform."""
    sens_name = config[CONF_NAME]
    sens_currency = config[CONF_CURRENCY]
    sens_region = config[CONF_REGION]

    sens_nordpool = NordpoolAPI(sens_name, sens_currency, sens_region)
    add_entities([sens_nordpool], True)


class NordpoolAPI(Entity):
    """Initiate communications to Nordpool API."""

    def __init__(self, sens_name, sens_currency, sens_region):
        """Init new sensor."""
        self._name = sens_name
        self._unit_of_measurement = CURRENCY_FRACTION[sens_currency]
        self._region = sens_region
        self._icon = ICON
        self._state = None
        self._currency = sens_currency
        self._day = None
        self._data = None
        self._device_state_attributes = {}

    def update(self):
        """Update sensor values."""
        from nordpool import elspot

        get_date = datetime.now()

        if get_date.day != self._day:
            nordpool_api = elspot.Prices(self._currency)

            area = self._region
            self._data = nordpool_api.hourly(end_date=get_date, areas=[area])
            self._day = get_date.day

        price_list = self._data

        hour = get_date.hour
        price = (price_list['areas'][area]['values'][hour]['value']/10)
        price_min = (price_list['areas'][area]['Min']/10)
        price_average = (price_list['areas'][area]['Average']/10)
        price_max = (price_list['areas'][area]['Max']/10)
        _LOGGER.debug("Nordpool day %s, hour %s", self._day, hour)
        _LOGGER.debug("Nordpool price: %s", price)
        _LOGGER.debug("Nordpool min: %s", price_min)
        _LOGGER.debug("Nordpool average: %s", price_average)
        _LOGGER.debug("Nordpool max: %s", price_max)
        self._state = round(price, 3)
        self._device_state_attributes = {'Min': round(price_min, 3),
                                         'Average': round(price_average, 3),
                                         'Max': round(price_max, 3),
                                         ATTR_ATTRIBUTION: ATTRIB}

    @property
    def name(self):
        """Name of the sensor."""
        return self._name

    @property
    def state(self):
        """Sensor state."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Sensor unit."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Sensor icon."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Device attributes."""
        return self._device_state_attributes
