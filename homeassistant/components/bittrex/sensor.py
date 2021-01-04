"""Example integration using DataUpdateCoordinator."""
import logging

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_BALANCES,
    CONF_TICKERS,
    CURRENCY_ICONS,
    DEFAULT_COIN_ICON,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Bittrex sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    for market in coordinator.data[CONF_TICKERS]:
        entities.append(Ticker(coordinator, market))

    if CONF_BALANCES in coordinator.data:
        for balance in coordinator.data[CONF_BALANCES]:
            entities.append(Balance(coordinator, balance))

    async_add_entities(entities, False)


class Ticker(CoordinatorEntity):
    """Implementation of the ticker sensor."""

    def __init__(self, coordinator, symbol):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._symbol = symbol
        self._currency = self._symbol.split("-")[0]
        self._unit_of_measurement = self._symbol.split("-")[1]

        self._name = f"Bittrex Ticker - {self._symbol}"
        self._unique_id = f"bittrex_ticker_{self._symbol})"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data[CONF_TICKERS][self._symbol]["lastTradeRate"]

    @property
    def unique_id(self):
        """Return a unique id for the sensor."""
        return self._unique_id

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return CURRENCY_ICONS.get(self._unit_of_measurement, DEFAULT_COIN_ICON)

    @property
    def device_state_attributes(self):
        """Return additional sensor state attributes."""
        return {
            "symbol": self._symbol,
            "last_trade_rate": self.coordinator.data[CONF_TICKERS][self._symbol][
                "lastTradeRate"
            ],
            "bid_rate": self.coordinator.data[CONF_TICKERS][self._symbol]["bidRate"],
            "ask_rate": self.coordinator.data[CONF_TICKERS][self._symbol]["askRate"],
            "currency": self._currency,
            "unit_of_measurement": self._unit_of_measurement,
        }


class Balance(CoordinatorEntity):
    """Implementation of the balance sensor."""

    def __init__(self, coordinator, balance):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._balance = balance

        self._name = f"Bittrex Balance - {self._balance}"
        self._unique_id = f"bittrex_balance_{self._balance})"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data[CONF_BALANCES][self._balance]["total"]

    @property
    def unique_id(self):
        """Return a unique id for the sensor."""
        return self._unique_id

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self.coordinator.data[CONF_BALANCES][self._balance]["currencySymbol"]

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return CURRENCY_ICONS.get(
            self.coordinator.data[CONF_BALANCES][self._balance]["currencySymbol"],
            DEFAULT_COIN_ICON,
        )

    @property
    def device_state_attributes(self):
        """Return additional sensor state attributes."""
        return {
            "currency_symbol": self.coordinator.data[CONF_BALANCES][self._balance][
                "currencySymbol"
            ],
            "available": self.coordinator.data[CONF_BALANCES][self._balance][
                "available"
            ],
            "updated_at": self.coordinator.data[CONF_BALANCES][self._balance][
                "updatedAt"
            ],
            "unit_of_measurement": self.coordinator.data[CONF_BALANCES][self._balance][
                "currencySymbol"
            ],
        }
