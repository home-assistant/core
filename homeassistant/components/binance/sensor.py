"""Example integration using DataUpdateCoordinator."""
import logging

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (  # CURRENCY_ICONS,; DEFAULT_COIN_ICON,
    CONF_BALANCES,
    CONF_CLOSED_ORDERS,
    CONF_OPEN_ORDERS,
    CONF_TICKERS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Binance sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    for market in coordinator.data[CONF_TICKERS]:
        entities.append(Ticker(coordinator, market))

    if CONF_BALANCES in coordinator.data:
        for balance in coordinator.data[CONF_BALANCES]:
            entities.append(Balance(coordinator, balance))

    if CONF_OPEN_ORDERS in coordinator.data:
        entities.append(OpenOrder(coordinator, coordinator.data[CONF_OPEN_ORDERS]))

    if CONF_CLOSED_ORDERS in coordinator.data:
        entities.append(ClosedOrder(coordinator, coordinator.data[CONF_CLOSED_ORDERS]))

    async_add_entities(entities, False)


class Ticker(CoordinatorEntity):
    """Implementation of the ticker sensor."""

    def __init__(self, coordinator, symbol):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._symbol = symbol
        # self._currency = self._symbol.split("-")[0]
        # self._unit_of_measurement = self._symbol.split("-")[1]

        self._name = f"BIN Ticker - {self._symbol}"
        self._unique_id = f"bin_ticker_{self._symbol})"

    def _get_data_property(self, property_name):
        """Return the property from self.coordinator.data."""
        return self.coordinator.data[CONF_TICKERS][self._symbol][property_name]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._get_data_property("lastPrice")

    @property
    def unique_id(self):
        """Return a unique id for the sensor."""
        return self._unique_id

    # @property
    # def unit_of_measurement(self):
    #     """Return the unit the value is expressed in."""
    #     return self._unit_of_measurement

    # @property
    # def icon(self):
    #     """Icon to use in the frontend."""
    #     return CURRENCY_ICONS.get(self._unit_of_measurement, DEFAULT_COIN_ICON)

    @property
    def device_state_attributes(self):
        """Return additional sensor state attributes."""
        return {
            "symbol": self._symbol,
            "last_price": self._get_data_property("lastPrice"),
            "bid_price": self._get_data_property("bidPrice"),
            "ask_price": self._get_data_property("askPrice"),
            # "currency": self._currency,
            # "unit_of_measurement": self._unit_of_measurement,
            "source": "Binance",
        }


class Balance(CoordinatorEntity):
    """Implementation of the balance sensor."""

    def __init__(self, coordinator, balance):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._balance = balance

        self._name = f"BIN Balance - {self._balance}"
        self._unique_id = f"bin_balance_{self._balance})"

    def _get_data_property(self, property_name):
        """Return the property from self.coordinator.data."""
        return self.coordinator.data[CONF_BALANCES][self._balance][property_name]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._get_data_property("free")

    @property
    def unique_id(self):
        """Return a unique id for the sensor."""
        return self._unique_id

    # @property
    # def unit_of_measurement(self):
    #     """Return the unit the value is expressed in."""
    #     return self._get_data_property("currencySymbol")

    # @property
    # def icon(self):
    #     """Icon to use in the frontend."""
    #     return CURRENCY_ICONS.get(
    #         self._get_data_property("currencySymbol"),
    #         DEFAULT_COIN_ICON,
    #     )

    @property
    def device_state_attributes(self):
        """Return additional sensor state attributes."""
        return {
            # "currency_symbol": self._get_data_property("currencySymbol"),
            "free": self._get_data_property("free"),
            "locked": self._get_data_property("locked"),
            # "unit_of_measurement": self._get_data_property("currencySymbol"),
            "source": "Binance",
        }


class Order(CoordinatorEntity):
    """Implementation of the order sensor."""

    def __init__(self, coordinator, order):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._order = order
        self._icon = "mdi:checkbook"

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return additional sensor state attributes."""
        return {
            "source": "Binance",
        }


class OpenOrder(Order):
    """Implementation of the open order sensor."""

    def __init__(self, coordinator, order):
        """Initialize the sensor."""
        super().__init__(coordinator, order)

        self._name = "BIN Orders - Open"
        self._unique_id = "bin_orders_open"

    def _get_data(self):
        """Return the data from self.coordinator.data."""
        return self.coordinator.data[CONF_OPEN_ORDERS]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return len(self._get_data())

    @property
    def unique_id(self):
        """Return a unique id for the sensor."""
        return self._unique_id


class ClosedOrder(Order):
    """Implementation of the closed order sensor."""

    def __init__(self, coordinator, order):
        """Initialize the sensor."""
        super().__init__(coordinator, order)

        self._name = "BIN Orders - Closed"
        self._unique_id = "bin_orders_closed"

    def _get_data(self):
        """Return the data from self.coordinator.data."""
        return self.coordinator.data[CONF_CLOSED_ORDERS]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return len(self._get_data())

    @property
    def unique_id(self):
        """Return a unique id for the sensor."""
        return self._unique_id
