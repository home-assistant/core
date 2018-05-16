"""
Support for Tibber.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.tibber/
"""
import asyncio

import logging

from datetime import timedelta
import aiohttp
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.util import dt as dt_util
from homeassistant.util import Throttle

REQUIREMENTS = ['pyTibber==0.4.1']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ACCESS_TOKEN): cv.string
})

ICON = 'mdi:currency-usd'
SCAN_INTERVAL = timedelta(minutes=1)
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up the Tibber sensor."""
    import tibber
    tibber_connection = tibber.Tibber(config[CONF_ACCESS_TOKEN],
                                      websession=async_get_clientsession(hass))

    try:
        await tibber_connection.update_info()
        dev = []
        for home in tibber_connection.get_homes():
            await home.update_info()
            dev.append(TibberSensor(home))
    except (asyncio.TimeoutError, aiohttp.ClientError):
        raise PlatformNotReady()

    async_add_devices(dev, True)


class TibberSensor(Entity):
    """Representation of an Tibber sensor."""

    def __init__(self, tibber_home):
        """Initialize the sensor."""
        self._tibber_home = tibber_home
        self._last_updated = None
        self._last_data_timestamp = None
        self._state = None
        self._is_available = False
        self._device_state_attributes = {}
        self._unit_of_measurement = self._tibber_home.price_unit
        self._name = 'Electricity price {}'.format(tibber_home.info['viewer']
                                                   ['home']['appNickname'])

    async def async_update(self):
        """Get the latest data and updates the states."""
        now = dt_util.now()
        if self._tibber_home.current_price_total and self._last_updated and \
           self._last_updated.hour == now.hour and self._last_data_timestamp:
            return

        if (not self._last_data_timestamp or
                (self._last_data_timestamp - now).total_seconds()/3600 < 12
                or not self._is_available):
            _LOGGER.debug("Asking for new data.")
            await self._fetch_data()

        self._is_available = self._update_current_price()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._device_state_attributes

    @property
    def available(self):
        """Return True if entity is available."""
        return self._is_available

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._unit_of_measurement

    @property
    def unique_id(self):
        """Return a unique ID."""
        home = self._tibber_home.info['viewer']['home']
        return home['meteringPointData']['consumptionEan']

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def _fetch_data(self):
        try:
            await self._tibber_home.update_info()
            await  self._tibber_home.update_price_info()
        except (asyncio.TimeoutError, aiohttp.ClientError):
            return
        data = self._tibber_home.info['viewer']['home']
        self._device_state_attributes['app_nickname'] = data['appNickname']
        self._device_state_attributes['grid_company'] = \
            data['meteringPointData']['gridCompany']
        self._device_state_attributes['estimated_annual_consumption'] = \
            data['meteringPointData']['estimatedAnnualConsumption']

    def _update_current_price(self):
        state = None
        max_price = 0
        min_price = 10000
        now = dt_util.now()
        for key, price_total in self._tibber_home.price_total.items():
            price_time = dt_util.as_local(dt_util.parse_datetime(key))
            price_total = round(price_total, 3)
            time_diff = (now - price_time).total_seconds()/60
            if (not self._last_data_timestamp or
                    price_time > self._last_data_timestamp):
                self._last_data_timestamp = price_time
            if 0 <= time_diff < 60:
                state = price_total
                self._last_updated = price_time
            if now.date() == price_time.date():
                max_price = max(max_price, price_total)
                min_price = min(min_price, price_total)
            self._state = state
            self._device_state_attributes['max_price'] = max_price
            self._device_state_attributes['min_price'] = min_price
        return state is not None
