"""Sensor for the Bitvavo integration."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BitvavoDataUpdateCoordinator
from .const import (
    ASSET_VALUE_BASE,
    ASSET_VALUE_CURRENCIES,
    ATTRIBUTION,
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

    entities = [
        Ticker(coordinator, market) for market in coordinator.data[CONF_TICKERS]
    ]

    if CONF_BALANCES in coordinator.data:
        for balance in coordinator.data[CONF_BALANCES]:
            entities.append(Balance(coordinator, balance))

        for currency in ASSET_VALUE_CURRENCIES:
            entities.append(TotalAssetValue(coordinator, currency))

    if CONF_OPEN_ORDERS in coordinator.data:
        entities.append(OpenOrders(coordinator, coordinator.data[CONF_OPEN_ORDERS]))

    async_add_entities(entities)


class Ticker(CoordinatorEntity, SensorEntity):
    """Implementation of the ticker sensor."""

    def __init__(self, coordinator: BitvavoDataUpdateCoordinator, symbol):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._symbol = symbol

        self._attr_icon = CURRENCY_ICONS.get(
            self._get_data_property("quote"), DEFAULT_COIN_ICON
        )
        self._attr_name = f"Bitvavo Ticker - {self._symbol}"
        self._attr_native_unit_of_measurement = self._get_data_property("quote")
        self._attr_unique_id = f"bitvavo_ticker_{self._symbol})"
        self._attr_extra_state_attributes = {
            "symbol": self._symbol,
            "bid_price": self._get_data_property("bid"),
            "ask_price": self._get_data_property("ask"),
            "bid_size": self._get_data_property("bidSize"),
            "ask_size": self._get_data_property("askSize"),
            "currency": self._get_data_property("base"),
            "quote_asset": self._get_data_property("quote"),
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    def _get_data_property(self, property_name):
        """Return the property from self.coordinator.data."""
        return self.coordinator.data[CONF_TICKERS][self._symbol][property_name]

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(float(self._get_data_property("price")), 4)


class Balance(CoordinatorEntity, SensorEntity):
    """Implementation of the balance sensor."""

    def __init__(self, coordinator: BitvavoDataUpdateCoordinator, balance):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._balance = balance

        self._attr_icon = CURRENCY_ICONS.get(
            self._get_data_property("symbol"), DEFAULT_COIN_ICON
        )
        self._attr_name = f"Bitvavo Balance - {self._balance}"
        self._attr_native_unit_of_measurement = self._get_data_property("symbol")
        self._attr_unique_id = f"bitvavo_balance_{self._balance})"
        self._attr_extra_state_attributes = {
            "available": self._get_data_property("available"),
            "in order": self._get_data_property("inOrder"),
            f"{ASSET_VALUE_BASE}_value".lower(): float(
                self._get_data_property("asset_value_in_base_asset")
            ),
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    def _get_data_property(self, property_name):
        """Return the property from self.coordinator.data."""
        return self.coordinator.data[CONF_BALANCES][self._balance][property_name]

    @property
    def state(self):
        """Return the state of the sensor."""
        state = float(self._get_data_property("available")) + float(
            self._get_data_property("inOrder")
        )
        return round(state, 4)


class OpenOrders(CoordinatorEntity, SensorEntity):
    """Implementation of the open orders sensor."""

    def __init__(self, coordinator: BitvavoDataUpdateCoordinator, order):
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._attr_icon = "mdi:format-list-bulleted"
        self._attr_name = "Bitvavo Open Orders"
        self._attr_native_unit_of_measurement = "Orders"
        self._attr_unique_id = "bitvavo_orders_open"
        self._attr_extra_state_attributes = {
            "buy orders": self._type_orders("buy"),
            "sell orders": self._type_orders("sell"),
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    def _get_orders(self):
        """Return the data from self.coordinator.data."""
        return self.coordinator.data[CONF_OPEN_ORDERS]

    def _type_orders(self, side):
        """Return the number of orders per type."""
        number = 0
        for order in self.coordinator.data[CONF_OPEN_ORDERS]:
            if order["side"] == side:
                number += 1

        return number

    @property
    def state(self):
        """Return the state of the sensor."""
        return len(self._get_orders())


class TotalAssetValue(CoordinatorEntity, SensorEntity):
    """Implementation of the total asset value sensor."""

    def __init__(self, coordinator: BitvavoDataUpdateCoordinator, currency):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._currency = currency

        self._attr_icon = CURRENCY_ICONS.get(self._currency, DEFAULT_COIN_ICON)
        self._attr_name = f"Bitvavo Total Asset Value - {self._currency.upper()}"
        self._attr_native_unit_of_measurement = self._currency
        self._attr_unique_id = f"bitvavo_total_asset_value_{self._currency.lower()}"
        self._attr_extra_state_attributes = {
            "note": f"Value is based on the last {self._currency}-{ASSET_VALUE_BASE} price of all coins in balance",
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    @property
    def state(self):
        """Return the state of the sensor."""
        total_base_asset_value = self.coordinator.data["total_base_asset"]

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
