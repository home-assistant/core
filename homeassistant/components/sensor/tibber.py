"""
Support for Tibber.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.tibber/
"""
import asyncio

import logging

from datetime import timedelta
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.util import dt as dt_util

REQUIREMENTS = ['pyTibber==0.2.1']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ACCESS_TOKEN): cv.string
})

ICON = 'mdi:currency-usd'
SCAN_INTERVAL = timedelta(minutes=1)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Tibber sensor."""
    import Tibber
    tibber = Tibber.Tibber(config[CONF_ACCESS_TOKEN],
                           websession=async_get_clientsession(hass))
    yield from tibber.update_info()
    dev = []
    for home in tibber.get_homes():
        yield from home.update_info()
        dev.append(TibberSensor(home))

    async_add_devices(dev)


class TibberSensor(Entity):
    """Representation of an Tibber sensor."""

    def __init__(self, tibber_home):
        """Initialize the sensor."""
        self._tibber_home = tibber_home
        self._last_updated = None
        self._state = None
        self._device_state_attributes = None
        self._unit_of_measurement = None
        self._name = 'Electricity price {}'.format(self._tibber_home.address1)

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data and updates the states."""
        if self._tibber_home.current_price_total and self._last_updated and \
           dt_util.as_utc(dt_util.parse_datetime(self._last_updated)).hour\
           == dt_util.utcnow().hour:
            return

        yield from self._tibber_home.update_current_price_info()

        self._state = self._tibber_home.current_price_total
        self._last_updated = self._tibber_home.current_price_info.\
            get('startsAt')
        self._device_state_attributes = self._tibber_home.current_price_info
        self._unit_of_measurement = self._tibber_home.price_unit

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._device_state_attributes

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
