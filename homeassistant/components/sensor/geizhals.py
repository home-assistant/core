"""
Parse prices of a device from geizhals.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.geizhals/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_NAME

REQUIREMENTS = ['geizhals==0.0.4']

_LOGGER = logging.getLogger(__name__)

CONF_DESCRIPTION = 'description'
CONF_PRODUCT_ID = 'product_id'
CONF_LOCALE = 'locale'

ICON = 'mdi:coin'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_PRODUCT_ID): cv.positive_int,
    vol.Optional(CONF_DESCRIPTION, default='Price'): cv.string,
    vol.Optional(CONF_LOCALE, default='DE'): vol.In(
        ['AT',
         'EU',
         'DE',
         'UK',
         'PL']),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Geizwatch sensor."""
    name = config.get(CONF_NAME)
    description = config.get(CONF_DESCRIPTION)
    product_id = config.get(CONF_PRODUCT_ID)
    domain = config.get(CONF_LOCALE)

    add_devices([Geizwatch(name, description, product_id, domain)],
                True)


class Geizwatch(Entity):
    """Implementation of Geizwatch."""

    def __init__(self, name, description, product_id, domain):
        """Initialize the sensor."""
        from geizhals import Geizhals

        self._name = name
        self.description = description
        self.product_id = product_id
        self.geizhals = Geizhals(product_id, domain)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the frontend."""
        return ICON

    @property
    def state(self):
        """Return the best price of the selected product."""
        return self.device.prices[0]

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        while len(self.device.prices) < 4:
            self.device.prices.append('None')
        attrs = {'device_name': self.device.name,
                 'description': self.description,
                 'unit_of_measurement': self.device.price_currency,
                 'product_id': self.product_id,
                 'price1': self.device.prices[0],
                 'price2': self.device.prices[1],
                 'price3': self.device.prices[2],
                 'price4': self.device.prices[3]}
        return attrs

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest price from geizhals and updates the state."""
        self.device = self.geizhals.parse()
