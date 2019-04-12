"""Support for watching multiple cryptocurrencies."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_ADDRESS, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['python-sochain-api==0.0.2']

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by chain.so"

CONF_NETWORK = 'network'

DEFAULT_NAME = 'Crypto Balance'

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Required(CONF_NETWORK): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the sochain sensors."""
    from pysochain import ChainSo
    address = config.get(CONF_ADDRESS)
    network = config.get(CONF_NETWORK)
    name = config.get(CONF_NAME)

    session = async_get_clientsession(hass)
    chainso = ChainSo(network, address, hass.loop, session)

    async_add_entities([SochainSensor(name, network.upper(), chainso)], True)


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
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    async def async_update(self):
        """Get the latest state of the sensor."""
        await self.chainso.async_get_data()
