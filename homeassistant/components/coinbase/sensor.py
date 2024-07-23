"""Support for Coinbase sensors."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CoinbaseData
from .const import (
    API_ACCOUNT_AMOUNT,
    API_ACCOUNT_BALANCE,
    API_ACCOUNT_CURRENCY,
    API_ACCOUNT_CURRENCY_CODE,
    API_ACCOUNT_ID,
    API_ACCOUNT_NAME,
    API_RATES,
    API_RESOURCE_TYPE,
    API_TYPE_VAULT,
    CONF_CURRENCIES,
    CONF_EXCHANGE_PRECISION,
    CONF_EXCHANGE_PRECISION_DEFAULT,
    CONF_EXCHANGE_RATES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

ATTR_NATIVE_BALANCE = "Balance in native currency"

CURRENCY_ICONS = {
    "BTC": "mdi:currency-btc",
    "ETH": "mdi:currency-eth",
    "EUR": "mdi:currency-eur",
    "LTC": "mdi:litecoin",
    "USD": "mdi:currency-usd",
}

DEFAULT_COIN_ICON = "mdi:cash"

ATTRIBUTION = "Data provided by coinbase.com"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Coinbase sensor platform."""
    instance: CoinbaseData = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[SensorEntity] = []

    provided_currencies: list[str] = [
        account[API_ACCOUNT_CURRENCY][API_ACCOUNT_CURRENCY_CODE]
        for account in instance.accounts
        if account[API_RESOURCE_TYPE] != API_TYPE_VAULT
    ]

    desired_currencies: list[str] = []

    if CONF_CURRENCIES in config_entry.options:
        desired_currencies = config_entry.options[CONF_CURRENCIES]

    exchange_base_currency: str = instance.exchange_rates[API_ACCOUNT_CURRENCY]

    exchange_precision: int = config_entry.options.get(
        CONF_EXCHANGE_PRECISION, CONF_EXCHANGE_PRECISION_DEFAULT
    )

    for currency in desired_currencies:
        if currency not in provided_currencies:
            _LOGGER.warning(
                (
                    "The currency %s is no longer provided by your account, please"
                    " check your settings in Coinbase's developer tools"
                ),
                currency,
            )
            continue
        entities.append(AccountSensor(instance, currency))

    if CONF_EXCHANGE_RATES in config_entry.options:
        entities.extend(
            ExchangeRateSensor(
                instance, rate, exchange_base_currency, exchange_precision
            )
            for rate in config_entry.options[CONF_EXCHANGE_RATES]
        )

    async_add_entities(entities)


class AccountSensor(SensorEntity):
    """Representation of a Coinbase.com sensor."""

    _attr_attribution = ATTRIBUTION

    def __init__(self, coinbase_data: CoinbaseData, currency: str) -> None:
        """Initialize the sensor."""
        self._coinbase_data = coinbase_data
        self._currency = currency
        for account in coinbase_data.accounts:
            if (
                account[API_ACCOUNT_CURRENCY][API_ACCOUNT_CURRENCY_CODE] != currency
                or account[API_RESOURCE_TYPE] == API_TYPE_VAULT
            ):
                continue
            self._attr_name = f"Coinbase {account[API_ACCOUNT_NAME]}"
            self._attr_unique_id = (
                f"coinbase-{account[API_ACCOUNT_ID]}-wallet-"
                f"{account[API_ACCOUNT_CURRENCY][API_ACCOUNT_CURRENCY_CODE]}"
            )
            self._attr_native_value = account[API_ACCOUNT_BALANCE][API_ACCOUNT_AMOUNT]
            self._attr_native_unit_of_measurement = account[API_ACCOUNT_CURRENCY][
                API_ACCOUNT_CURRENCY_CODE
            ]
            self._attr_icon = CURRENCY_ICONS.get(
                account[API_ACCOUNT_CURRENCY][API_ACCOUNT_CURRENCY_CODE],
                DEFAULT_COIN_ICON,
            )
            self._native_balance = round(
                float(account[API_ACCOUNT_BALANCE][API_ACCOUNT_AMOUNT])
                / float(coinbase_data.exchange_rates[API_RATES][currency]),
                2,
            )
            break

        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.coinbase.com/settings/api",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._coinbase_data.user_id)},
            manufacturer="Coinbase.com",
            name=f"Coinbase {self._coinbase_data.user_id[-4:]}",
        )

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the state attributes of the sensor."""
        return {
            ATTR_NATIVE_BALANCE: f"{self._native_balance} {self._coinbase_data.exchange_base}",
        }

    def update(self) -> None:
        """Get the latest state of the sensor."""
        self._coinbase_data.update()
        for account in self._coinbase_data.accounts:
            if (
                account[API_ACCOUNT_CURRENCY][API_ACCOUNT_CURRENCY_CODE]
                != self._currency
                or account[API_RESOURCE_TYPE] == API_TYPE_VAULT
            ):
                continue
            self._attr_native_value = account[API_ACCOUNT_BALANCE][API_ACCOUNT_AMOUNT]
            self._native_balance = round(
                float(account[API_ACCOUNT_BALANCE][API_ACCOUNT_AMOUNT])
                / float(self._coinbase_data.exchange_rates[API_RATES][self._currency]),
                2,
            )
            break


class ExchangeRateSensor(SensorEntity):
    """Representation of a Coinbase.com sensor."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coinbase_data: CoinbaseData,
        exchange_currency: str,
        exchange_base: str,
        precision: int,
    ) -> None:
        """Initialize the sensor."""
        self._coinbase_data = coinbase_data
        self._currency = exchange_currency
        self._attr_name = f"{exchange_currency} Exchange Rate"
        self._attr_unique_id = (
            f"coinbase-{coinbase_data.user_id}-xe-{exchange_currency}"
        )
        self._precision = precision
        self._attr_icon = CURRENCY_ICONS.get(exchange_currency, DEFAULT_COIN_ICON)
        self._attr_native_value = round(
            1 / float(coinbase_data.exchange_rates[API_RATES][exchange_currency]),
            precision,
        )
        self._attr_native_unit_of_measurement = exchange_base
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.coinbase.com/settings/api",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._coinbase_data.user_id)},
            manufacturer="Coinbase.com",
            name=f"Coinbase {self._coinbase_data.user_id[-4:]}",
        )

    def update(self) -> None:
        """Get the latest state of the sensor."""
        self._coinbase_data.update()
        self._attr_native_value = round(
            1 / float(self._coinbase_data.exchange_rates.rates[self._currency]),
            self._precision,
        )
