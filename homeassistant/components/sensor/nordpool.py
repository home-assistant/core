# -*- coding: utf-8 -*-
"""
Sensor to display the current power prices from NordPool.

To enable the sensor, add this to the config.yaml file under sensors:

sensor:
  - platform: nordpool
    currency: 'NOK'
    region: 'Kr.sand'

The available currencies are EUR, DKK, NOK and SEK.

The available regions are DK1, DK2, EE, FI, LT, LV, Oslo, Kr.sand, Bergen,
Molde, Tr.heim, Tromsø, SE1, SE2, SE3, SE4 and SYS.

Optional parameters are:
    name: 'Elspot kWh'
    offset: '01:00:00'

You may use the offset to adjust the "current price" to indicate the price
at an offset. Positive offset give you future prices, and negative offset
give you past prices.
"""
import datetime
import logging
# pylint: disable=E0611
from random import randrange
# pylint: enable=E0611
import requests
import voluptuous
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (ATTR_ATTRIBUTION, CONF_CURRENCY, CONF_OFFSET,
                                 CONF_REGION, CONF_NAME)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

_CURRENCY_LIST = ['DKK', 'EUR', 'NOK', 'SEK']

_CURRENCY_FRACTION = {
    'DKK': 'Øre',
    'EUR': 'Cent',
    'NOK': 'Øre',
    'SEK': 'Öre'
}

_REGION_NAME = ['DK1', 'DK2', 'EE', 'FI', 'LT', 'LV', 'Oslo', 'Kr.sand',
                'Bergen', 'Molde', 'Tr.heim', 'Tromsø', 'SE1', 'SE2', 'SE3',
                'SE4', 'SYS']

DEFAULT_CURRENCY = 'EUR'
DEFAULT_REGION = 'SYS'
DEFAULT_NAME = 'Elspot kWh'

_TODAY = 0
_TOMORROW = 1

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    voluptuous.Optional(CONF_CURRENCY, default=DEFAULT_CURRENCY):
        voluptuous.In(_CURRENCY_LIST),
    voluptuous.Optional(CONF_REGION, default=DEFAULT_REGION):
        voluptuous.In(_REGION_NAME),
    voluptuous.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    voluptuous.Optional(CONF_OFFSET, default=0): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Get the platform settings and setup the sensor."""
    currency = config.get(CONF_CURRENCY)
    region = config.get(CONF_REGION)
    name = config.get(CONF_NAME)
    offset = config.get(CONF_OFFSET)
    add_devices([Nordpool(name, currency, region, offset)])


class Nordpool(Entity):
    """The Nordpool platform."""

    def __init__(self, name, currency, region, offset):
        """Initialize the sensor."""
        self._prices = [None, None, None, None, None, None, None, None,
                        None, None, None, None, None, None, None, None,
                        None, None, None, None, None, None, None, None,
                        0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self._tomorrow = [None, None, None, None, None, None, None, None,
                          None, None, None, None, None, None, None, None,
                          None, None, None, None, None, None, None, None,
                          0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self._day = [99, 99]
        self._next = [0, 0]
        self._state = None
        self._name = name
        self._available = False
        self._failed_fetch = [0, 0]
        self._min = 0
        self._max = 0
        self._average = 0
        self._peak = 0
        self._off_peak1 = 0
        self._off_peak2 = 0
        self._offset = int(offset.split(':')[0])

        # Setup the currency fraction as unit.
        self._currency = currency
        self._currency_fraction = _CURRENCY_FRACTION[currency]

        # Setup region name for correct prices.
        self._region = region

        # Fetch today's prices.
        self.fetch_new_data(_TODAY)
        # Initiate the first value
        now = datetime.datetime.now() + datetime.timedelta(hours=self._offset)
        self._state = self._prices[now.hour]

    @property
    def available(self):
        """Return the availability of the sensor."""
        return self._available

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the current power price from Nordpool if available."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the correct currency."""
        return self._currency_fraction

    @property
    def device_state_attributes(self):
        """Return aditional price information."""
        return {
            'Min': self._min,
            'Max': self._max,
            'Average': self._average,
            'Peak': self._peak,
            'Off-peak1': self._off_peak1,
            'Off-peak2': self._off_peak2,
            'next update': str(self._next[0]) + ':' + str(self._next[1]),
            ATTR_ATTRIBUTION: "For details, see https://www.nordpoolgroup.com/"
        }

    def update(self):
        """Update the price to the current price."""
        now = datetime.datetime.now() + datetime.timedelta(hours=self._offset)
        # If the current day is a new day, update the data.
        if self._day[_TODAY] != int(now.day) and \
                self._day[_TOMORROW] == int(now.day):
            self._prices = list(self._tomorrow)
            self._day[_TODAY] = self._day[_TOMORROW]
            self._day[_TOMORROW] = 99

        if self._day[_TODAY] != int(now.day):
            # Fetch today's prices if the current data is invalid.
            self.fetch_new_data(_TODAY)

        # Fetch new data if it is time to do so.
        tomorrow = now + datetime.timedelta(days=1)
        if ((now.hour > self._next[0] or (now.hour >= self._next[0] and
                                          now.minute >= self._next[1])) and
                self._day[_TOMORROW] != tomorrow.day):
            self.fetch_new_data(_TOMORROW)

        # Update the current price if the price-table is valid
        self._available = False
        if self._prices[now.hour] is not None:
            self._available = True
            self._state = self._prices[now.hour]
            self._min = self._prices[24]
            self._max = self._prices[25]
            self._average = self._prices[26]
            self._peak = self._prices[27]
            self._off_peak1 = self._prices[28]
            self._off_peak2 = self._prices[29]

    def fetch_new_data(self, selected_day):
        """Collect the current prices from Nordpool."""
        now = datetime.datetime.now() + datetime.timedelta(hours=self._offset)
        if selected_day == _TOMORROW:
            now += datetime.timedelta(days=1)
        date_to_fetch = now.strftime("%d-%m-%Y")

        _LOGGER.debug("Fetching Nordpool prices.")

        new_data = [None, None, None, None, None, None, None, None, None, None,
                    None, None, None, None, None, None, None, None, None, None,
                    None, None, None, None,
                    0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

        self._failed_fetch[selected_day] += 1

        # If the fetching failed more than two times, set all values to None,
        # and set the date to the requested date.
        if self._failed_fetch[selected_day] > 2:
            self._day[selected_day] = int(date_to_fetch[:2])
            if selected_day == _TODAY:
                self._prices = list(new_data)
            else:
                self._tomorrow = list(new_data)

        url = "http://www.nordpoolspot.com/api/marketdata/page/10"

        params = dict(currency=self._currency,
                      endDate=date_to_fetch)
        date = "Failed"

        resp = requests.get(url=url, params=params)

        data = resp.json()

        row = 0

        data = data['data']
        for rows in data['Rows']:
            for col in rows['Columns']:
                if col['Name'] == self._region:
                    price = col['Value']
                    price = price.replace(',', '.')
                    price = price.replace(' ', '')
                    if "." not in price:
                        new_data[row] = 0.0
                    else:
                        new_data[row] = round(float(price) / 10, 3)
            row = row + 1
        date = data['DataStartdate']

        # Check for success, and prepare for the next update
        if date[8:10] == date_to_fetch[:2]:
            self._day[selected_day] = int(date[8:10])
            self._failed_fetch[selected_day] = 0
            if selected_day == _TODAY:
                self._prices = list(new_data)
            else:
                self._tomorrow = list(new_data)
            _LOGGER.debug("Nordpool prices updated.")
        else:
            _LOGGER.error("Nordpool price fetch failed for %s. %s, %d.",
                          str(date_to_fetch), "Attempt number:",
                          str(self._failed_fetch))

        self._next[0] = randrange(16, 23)
        self._next[1] = randrange(60)
