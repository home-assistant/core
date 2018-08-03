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
from homeassistant.const import (CONF_DOMAIN, CONF_NAME)

REQUIREMENTS = ['beautifulsoup4==4.6.1']
_LOGGER = logging.getLogger(__name__)

CONF_PRODUCT_ID = 'product_id'
CONF_DESCRIPTION = 'description'
CONF_REGEX = 'regex'

ICON = 'mdi:coin'
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_PRODUCT_ID): cv.positive_int,
    vol.Optional(CONF_DESCRIPTION, default='Price'): cv.string,
    vol.Optional(CONF_DOMAIN, default='geizhals.de'): vol.In(
        ['geizhals.at',
         'geizhals.eu',
         'geizhals.de',
         'skinflint.co.uk',
         'cenowarka.pl']),
    vol.Optional(CONF_REGEX, default=r'\D\s(\d*)[\,|\.](\d*)'): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Geizwatch sensor."""
    name = config.get(CONF_NAME)
    description = config.get(CONF_DESCRIPTION)
    product_id = config.get(CONF_PRODUCT_ID)
    domain = config.get(CONF_DOMAIN)
    regex = config.get(CONF_REGEX)

    add_devices([Geizwatch(name, description, product_id, domain, regex)],
                True)


class Geizwatch(Entity):
    """Implementation of Geizwatch."""

    def __init__(self, name, description, product_id, domain,
                 regex):
        """Initialize the sensor."""
        self._name = name
        self.description = description
        self.data = GeizParser(product_id, domain, regex)
        self._state = None

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
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        while len(self.data.prices) < 4:
            self.data.prices.append("None")
        attrs = {'device_name': self.data.device_name,
                 'description': self.description,
                 'unit_of_measurement': self.data.unit_of_measurement,
                 'product_id': self.data.product_id,
                 'price1': self.data.prices[0],
                 'price2': self.data.prices[1],
                 'price3': self.data.prices[2],
                 'price4': self.data.prices[3]}
        return attrs

    def update(self):
        """Get the latest price from geizhals and updates the state."""
        self.data.update()
        self._state = self.data.prices[0]


class GeizParser:
    """Pull data from the geizhals website."""

    def __init__(self, product_id, domain, regex):
        """Initialize the sensor."""
        # parse input arguments
        self.product_id = product_id
        self.domain = domain
        self.regex = regex

        # set some empty default values
        self.device_name = ''
        self.prices = [None, None, None, None]
        self.unit_of_measurement = ''

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update the device prices."""
        import bs4
        import requests
        import re

        sess = requests.session()
        request = sess.get('https://{}/{}'.format(self.domain,
                                                  self.product_id),
                           allow_redirects=True,
                           timeout=1)
        soup = bs4.BeautifulSoup(request.text, 'html.parser')

        # parse name
        raw = soup.find_all('span', attrs={'itemprop': 'name'})
        self.device_name = raw[1].string

        # parse prices
        prices = []
        for tmp in soup.find_all('span', attrs={'class': 'gh_price'}):
            matches = re.search(self.regex, tmp.string)
            raw = '{}.{}'.format(matches.group(1),
                                 matches.group(2))
            prices += [float(raw)]
        prices.sort()
        self.prices = prices[1:]

        # parse unit
        price_match = soup.find('span', attrs={'class': 'gh_price'})
        matches = re.search(r'€|£|PLN', price_match.string)
        self.unit_of_measurement = matches.group()
