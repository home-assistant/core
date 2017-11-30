"""
Currency exchange rate support that comes from fixer.io.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.fixer/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, ATTR_ATTRIBUTION, CONF_BASE)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['fixerio==0.1.1']

_LOGGER = logging.getLogger(__name__)

ATTR_BASE = 'Base currency'
ATTR_EXCHANGE_RATE = 'Exchange rate'
ATTR_TARGET = 'Target currency'

CONF_ATTRIBUTION = "Data provided by the European Central Bank (ECB)"
CONF_TARGET = 'target'

DEFAULT_BASE = 'USD'
DEFAULT_NAME = 'Exchange rate'

ICON = 'mdi:currency'

SCAN_INTERVAL = timedelta(days=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TARGET): cv.string,
    vol.Optional(CONF_BASE, default=DEFAULT_BASE): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Fixer.io sensor."""
    from fixerio import (Fixerio, exceptions)

    name = config.get(CONF_NAME)
    base = config.get(CONF_BASE)
    target = config.get(CONF_TARGET)

    try:
        Fixerio(base=base, symbols=[target], secure=True).latest()
    except exceptions.FixerioException:
        _LOGGER.error("One of the given currencies is not supported")
        return False

    data = ExchangeData(base, target)
    add_devices([ExchangeRateSensor(data, name, target)], True)


class ExchangeRateSensor(Entity):
    """Representation of a Exchange sensor."""

    def __init__(self, data, name, target):
        """Initialize the sensor."""
        self.data = data
        self._target = target
        self._name = name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._target

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.data.rate is not None:
            return {
                ATTR_BASE: self.data.rate['base'],
                ATTR_TARGET: self._target,
                ATTR_EXCHANGE_RATE: self.data.rate['rates'][self._target],
                ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            }

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data and updates the states."""
        self.data.update()
        self._state = round(self.data.rate['rates'][self._target], 3)


class ExchangeData(object):
    """Get the latest data and update the states."""

    def __init__(self, base_currency, target_currency):
        """Initialize the data object."""
        from fixerio import Fixerio

        self.rate = None
        self.base_currency = base_currency
        self.target_currency = target_currency
        self.exchange = Fixerio(
            base=self.base_currency, symbols=[self.target_currency],
            secure=True)

    def update(self):
        """Get the latest data from Fixer.io."""
        self.rate = self.exchange.latest()
