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
import homeassistant.util.dt as dt_util

import bs4
import requests
import re

REQUIREMENTS = ['beautifulsoup4==4.5.3', 'requests==2.14.2']
_LOGGER = logging.getLogger(__name__)

CONF_name = 'name'
CONF_friendly_name = 'friendly_name'
CONF_product_id = 'product_id'
CONF_protocol = 'protocol'
CONF_domain = 'domain'
CONF_regex = 'regex'

ICON = 'mdi:coin'
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_name): cv.string,
    vol.Required(CONF_friendly_name, default='Preis'): cv.string,
    vol.Required(CONF_product_id): cv.positive_int,
    vol.Optional(CONF_protocol, default='https'): vol.In(['https', 'http']),
    vol.Optional(CONF_domain, default='geizhals.de'): vol.In(['geizhals.at',
                                                              'geizhals.eu',
                                                              'geizhals.de',
                                                              'skinflint.co.uk',
                                                              'cenowarka.pl']),
    vol.Optional(CONF_regex, default='\D\s(\d*)[\,|\.](\d*)'): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Geizwatch Sensor."""
    name = config.get(CONF_name)
    friendly_name = config.get(CONF_friendly_name)
    product_id = config.get(CONF_product_id)
    protocol = config.get(CONF_protocol)
    domain = config.get(CONF_domain)
    regex = config.get(CONF_regex)

    add_devices([Geizwatch(name, friendly_name, product_id, protocol, domain, regex)])


class Geizwatch(Entity):
    """Implementation of Geizwatch."""

    def __init__(self, name, friendly_name, product_id, protocol, domain, regex):
        """Initialize the sensor."""
        self._name = name
        self.friendly_name = friendly_name
        self.data = GeizParser(product_id, protocol, domain, regex)
        self.update()

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
        attrs = {'device_name': self.data.device_name,
                 'friendly_name': self.friendly_name,
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


class GeizParser(object):
    """Pull data from the geizhals web page."""

    def __init__(self, product_id, protocol, domain, regex):
        """Initialize the sensor."""
        # parse input arguments
        self.product_id = product_id
        self.protocol = protocol
        self.domain = domain
        self.regex = regex

        # set some empty default values
        self.device_name = ''
        self.prices = []
        self.unit_of_measurement = ''

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update the device prices."""
        sess = requests.session()
        r = sess.get('{}://{}/{}'.format(self.protocol, self.domain, self.product_id), allow_redirects=True)
        soup = bs4.BeautifulSoup(r.text, 'html.parser')

        # parse name
        self.device_name = soup.find_all('span', attrs={'itemprop': 'name'})[1].string

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
        self.unit_of_measurement = re.search(r'€|£|PLN', tmp.string)[0]
