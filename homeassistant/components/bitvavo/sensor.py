"""Example integration using DataUpdateCoordinator."""
import logging

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ASSET_VALUE_BASE,
    ASSET_VALUE_CURRENCIES,
    CONF_ASSET_TICKERS,
    CONF_BALANCES,
    CONF_OPEN_ORDERS,
    CONF_TICKERS,
    CURRENCY_ICONS,
    DEFAULT_COIN_ICON,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Bitvavo sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    for market in coordinator.data[CONF_TICKERS]:
        entities.append(Ticker(coordinator, market))

    if CONF_BALANCES in coordinator.data:
        for balance in coordinator.data[CONF_BALANCES]:
            if coordinator.data[CONF_BALANCES][balance]["available"] > "0":
                entities.append(Balance(coordinator, balance))

        for currency in ASSET_VALUE_CURRENCIES:
            entities.append(TotalAssetValue(coordinator, currency))

    if CONF_OPEN_ORDERS in coordinator.data:
        entities.append(OpenOrder(coordinator, coordinator.data[CONF_OPEN_ORDERS]))

    async_add_entities(entities, False)


class Ticker(CoordinatorEntity):
    """Implementation of the ticker sensor."""

    def __init__(self, coordinator, symbol):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._symbol = symbol

        self._name = f"Bitvavo Ticker - {self._symbol}"
        self._unique_id = f"bitvavo_ticker_{self._symbol})"

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
        return round(float(self._get_data_property("price")), 4)

    @property
    def unique_id(self):
        """Return a unique id for the sensor."""
        return self._unique_id

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._get_data_property("quote")

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return CURRENCY_ICONS.get(self.unit_of_measurement, DEFAULT_COIN_ICON)

    @property
    def device_state_attributes(self):
        """Return additional sensor state attributes."""
        return {
            "symbol": self._symbol,
            "bid_price": self._get_data_property("bid"),
            "ask_price": self._get_data_property("ask"),
            "bid_size": self._get_data_property("bidSize"),
            "ask_size": self._get_data_property("askSize"),
            "currency": self._get_data_property("base"),
            "quote_asset": self._get_data_property("quote"),
            "unit_of_measurement": self.unit_of_measurement,
            "source": "Bitvavo",
        }


class Balance(CoordinatorEntity):
    """Implementation of the balance sensor."""

    def __init__(self, coordinator, balance):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._balance = balance

        self._name = f"Bitvavo Balance - {self._balance}"
        self._unique_id = f"bitvavo_balance_{self._balance})"

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
        state = float(self._get_data_property("available")) + float(
            self._get_data_property("inOrder")
        )
        return round(state, 4)

    @property
    def unique_id(self):
        """Return a unique id for the sensor."""
        return self._unique_id

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._get_data_property("symbol")

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return CURRENCY_ICONS.get(self.unit_of_measurement, DEFAULT_COIN_ICON)

    @property
    def device_state_attributes(self):
        """Return additional sensor state attributes."""
        return {
            "available": self._get_data_property("available"),
            "in order": self._get_data_property("inOrder"),
            f"{ASSET_VALUE_BASE}_value".lower(): float(
                self._get_data_property("asset_value_in_base_asset")
            ),
            "unit_of_measurement": self._get_data_property("symbol"),
            "source": "Bitvavo",
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
            "source": "Bitvavo",
        }


class OpenOrder(Order):
    """Implementation of the open order sensor."""

    def __init__(self, coordinator, order):
        """Initialize the sensor."""
        super().__init__(coordinator, order)

        self._name = "Bitvavo Orders - Open"
        self._unique_id = "bitvavo_orders_open"

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

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return "Orders"


class TotalAssetValue(CoordinatorEntity):
    """Implementation of the total asset value sensor."""

    def __init__(self, coordinator, currency):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._currency = currency

        self._name = f"Bitvavo Total Asset Value - {self._currency.upper()}"
        self._unique_id = f"bitvavo_total_asset_value_{self._currency.lower()}"
        self._icon = CURRENCY_ICONS.get(self.unit_of_measurement, DEFAULT_COIN_ICON)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        total_base_asset_value = 0.0

        for i in self.coordinator.data[CONF_BALANCES].keys():
            try:
                asset_value = self.coordinator.data[CONF_BALANCES][i][
                    "asset_value_in_base_asset"
                ]

                total_base_asset_value += float(asset_value)
            except KeyError:
                continue

        if self._currency == ASSET_VALUE_BASE:
            total_asset_value = total_base_asset_value
        else:
            asset_value_pair_name = (self._currency + "-" + ASSET_VALUE_BASE).upper()
            last_price = float(
                self.coordinator.data[CONF_ASSET_TICKERS][asset_value_pair_name][
                    "price"
                ]
            )

            total_asset_value = total_base_asset_value / last_price

        return round(total_asset_value, 4)

    @property
    def unique_id(self):
        """Return a unique id for the sensor."""
        return self._unique_id

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._currency

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return self._icon

    @property
    def extra_state_attributes(self):
        """Return additional sensor state attributes."""
        return {
            "note": f"Value is based on the last {self._currency}-{ASSET_VALUE_BASE} price of every coin in balance",
            "source": "Bitvavo",
        }
