"""
Support for watching multiple cryptocurrencies.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.sochain/
"""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, ATTR_ATTRIBUTION)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.aiohttp_client import async_get_clientsession

REQUIREMENTS = ['python-sochain-api==0.0.2']

_LOGGER = logging.getLogger(__name__)

CONF_ADDRESS = 'address'
CONF_NETWORK = 'network'
CONF_ATTRIBUTION = "Data provided by chain.so"

DEFAULT_NAME = 'Crypto Balance'

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Required(CONF_NETWORK): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the sochain sensors."""
    from pysochain import ChainSo
    address = config.get(CONF_ADDRESS)
    network = config.get(CONF_NETWORK)
    name = config.get(CONF_NAME)

    session = async_get_clientsession(hass)
    chainso = ChainSo(network, address, hass.loop, session)

    async_add_devices([SochainSensor(name, network.upper(), chainso)], True)


class SochainSensor(Entity):
    """Representation of a Sochain sensor."""

    def __init__(self, name, unit_of_measurement, chainso):
        """Initialize the sensor."""
        self._name = name
        self._unit_of_measurement = unit_of_measurement
        self.chainso = chainso

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.chainso.data.get("confirmed_balance") \
            if self.chainso is not None else None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
        }

    @asyncio.coroutine
    def async_update(self):
        """Get the latest state of the sensor."""
        yield from self.chainso.async_get_data()
