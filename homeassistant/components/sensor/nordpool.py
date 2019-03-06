"""
Support for Nordpool electrical prices sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.nordpool/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (ATTR_ATTRIBUTION,
                                 CONF_NAME,
                                 CONF_CURRENCY,
                                 CONF_REGION)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from datetime import timedelta

REQUIREMENTS = ['nordpool==0.2']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

CURRENCY_FRACTION = {
    'DKK': 'Øre',
    'EUR': 'Cent',
    'NOK': 'Øre',
    'SEK': 'Øre'
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_CURRENCY): cv.string,
    vol.Required(CONF_REGION): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Setup Nordpool sensor."""
    sens_name = config[CONF_NAME]
    sens_currency = config[CONF_CURRENCY]
    sens_region = config[CONF_REGION]

    sens_nordpool = NordpoolAPI(sens_name, sens_currency, sens_region)
    add_entities([sens_nordpool], True)


class NordpoolAPI(Entity):
    """Initiate communications to Nordpool API."""

    def __init__(self, sens_name, sens_currency, sens_region):
        """Init new sensor."""
        _LOGGER.debug("Init sensor")
        self._name = sens_name
        self._unit_of_measurement = CURRENCY_FRACTION[sens_currency]
        self._region = sens_region
        self._icon = 'mdi:cash-usd'
        self._state = None
        self._currency = sens_currency
        self._price_min = None
        self._price_average = None
        self._price_max = None

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Update sensor values."""
        from nordpool import elspot
        from datetime import datetime

        nordpool_api = elspot.Prices()
        nordpool_api.currency = self._currency

        get_date = datetime.now()
        area = self._region
        price_list = nordpool_api.hourly(end_date=get_date, areas=[area])

        hour = get_date.hour
        price = (price_list['areas'][area]['values'][hour]['value']/10)
        self._price_min = (price_list['areas'][area]['Min']/10)
        self._price_average = (price_list['areas'][area]['Average']/10)
        self._price_max = (price_list['areas'][area]['Max']/10)
        _LOGGER.debug("Nordpool hour: %s", hour)
        _LOGGER.debug("Nordpool price: %s", price)
        _LOGGER.debug("Nordpool min: %s", self._price_min)
        _LOGGER.debug("Nordpool average: %s", self._price_average)
        _LOGGER.debug("Nordpool max: %s", self._price_max)
        self._state = round(price, 3)

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
        a = {'Min': round(self._price_min, 3),
             'Avarage': round(self._price_average, 3),
             'Max': round(self._price_max, 3),
             ATTR_ATTRIBUTION: "For details, see https://nordpoolgroup.com/"}

        return a
