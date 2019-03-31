"""
Stock market information from Alpha Vantage.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.alpha_vantage/
"""
import logging

from homeassistant.const import (ATTR_ATTRIBUTION, CONF_CURRENCY, CONF_NAME)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from . import (
    CONF_SYMBOLS,
    CONF_SYMBOL,
    DOMAIN as ALPHA_VANTAGE,
    STOCK_DATA_UPDATED,
    FOREX_DATA_UPDATED,
    CONF_FOREIGN_EXCHANGE, CONF_FROM, CONF_TO)

DEPENDENCIES = ['alpha_vantage']

_LOGGER = logging.getLogger(__name__)

ATTR_CLOSE = 'close'
ATTR_HIGH = 'high'
ATTR_LOW = 'low'
ATTR_FROM = 'from'
ATTR_TO = 'to'

ATTRIBUTION = "Stock market information provided by Alpha Vantage"

ICONS = {
    'BTC': 'mdi:currency-btc',
    'EUR': 'mdi:currency-eur',
    'GBP': 'mdi:currency-gbp',
    'INR': 'mdi:currency-inr',
    'RUB': 'mdi:currency-rub',
    'TRY': 'mdi:currency-try',
    'USD': 'mdi:currency-usd',
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Alpha Vantage sensor."""
    data = hass.data[ALPHA_VANTAGE]

    dev = []
    for symbol in discovery_info[CONF_SYMBOLS]:
        dev.append(AlphaVantageSensor(symbol, data))

    for conversion in discovery_info[CONF_FOREIGN_EXCHANGE]:
        dev.append(AlphaVantageForeignExchange(conversion, data))

    add_entities(dev, True)


class AlphaVantageSensor(Entity):
    """Representation of a Alpha Vantage sensor."""

    def __init__(self, symbol, data):
        """Initialize the sensor."""
        self._symbol = symbol[CONF_SYMBOL]
        self._name = symbol.get(CONF_NAME, self._symbol)
        self._data = data
        self.values = None
        self._unit_of_measurement = symbol.get(CONF_CURRENCY, self._symbol)
        self._icon = ICONS.get(symbol.get(CONF_CURRENCY, 'USD'))

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.values['price']

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

        if self.values.get(ATTR_CLOSE):
            attributes[ATTR_CLOSE] = self.values.get(ATTR_CLOSE)
        if self.values.get(ATTR_HIGH):
            attributes[ATTR_HIGH] = self.values.get(ATTR_HIGH)
        if self.values.get(ATTR_LOW):
            attributes[ATTR_LOW] = self.values.get(ATTR_LOW)

        return attributes

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def should_poll(self):
        """Return the polling requirement for this sensor."""
        return False

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        async_dispatcher_connect(
            self.hass, STOCK_DATA_UPDATED, self._schedule_immediate_update
        )

    def update(self):
        """Get the latest data and updates the states."""
        self.values = self._data.stock_quotes[self._symbol]

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)


class AlphaVantageForeignExchange(Entity):
    """Sensor for foreign exchange rates."""

    def __init__(self, config, data):
        """Initialize the sensor."""
        self._key = config[CONF_FROM], config[CONF_TO]
        self._name = config.get(CONF_NAME, '{}/{}'.format(*self._key))
        self._unit_of_measurement = self._key[1]
        self._icon = ICONS.get(self._key[0], 'USD')
        self._data = data
        self.values = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(float(self.values['Exchange Rate']), 4)

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.values is not None:
            return {
                ATTR_ATTRIBUTION: ATTRIBUTION,
                ATTR_FROM: self._key[0],
                ATTR_TO: self._key[1],
            }

    @property
    def should_poll(self):
        """Return the polling requirement for this sensor."""
        return False

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        async_dispatcher_connect(
            self.hass, FOREX_DATA_UPDATED, self._schedule_immediate_update
        )

    def update(self):
        """Get the latest data and updates the states."""
        self.values = self._data.forex_quotes[self._key]

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)
