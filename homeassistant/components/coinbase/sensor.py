"""Support for Coinbase sensors."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION

from .const import CONF_CURRENCIES, CONF_EXCAHNGE_RATES, DOMAIN

ATTR_NATIVE_BALANCE = "Balance in native currency"

CURRENCY_ICONS = {
    "BTC": "mdi:currency-btc",
    "ETH": "mdi:currency-eth",
    "EUR": "mdi:currency-eur",
    "LTC": "mdi:litecoin",
    "USD": "mdi:currency-usd",
}

DEFAULT_COIN_ICON = "mdi:currency-usd-circle"

ATTRIBUTION = "Data provided by coinbase.com"

DATA_COINBASE = "coinbase_cache"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Coinbase sensor platform."""
    instance = hass.data[DOMAIN][config_entry.entry_id]
    hass.async_add_executor_job(instance.update)

    entities = []
    exchange_native_currency = instance.exchange_rates.currency
    for currency in config_entry.data[CONF_CURRENCIES]:
        entities.append(AccountSensor(instance, currency))
    for rate in config_entry.data[CONF_EXCAHNGE_RATES]:
        entities.append(
            ExchangeRateSensor(
                instance,
                rate,
                exchange_native_currency,
            )
        )

    async_add_entities(entities)


class AccountSensor(SensorEntity):
    """Representation of a Coinbase.com sensor."""

    def __init__(self, coinbase_data, currency):
        """Initialize the sensor."""
        self._coinbase_data = coinbase_data
        self._currency = currency
        for account in coinbase_data.accounts["data"]:
            if account.currency == currency:
                self._name = f"Coinbase {account['name']}"
                self._state = account["balance"]["amount"]
                self._unit_of_measurement = account.currency
                self._native_balance = account["native_balance"]["amount"]
                self._native_currency = account["native_balance"]["currency"]
                break

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return CURRENCY_ICONS.get(self._unit_of_measurement, DEFAULT_COIN_ICON)

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_NATIVE_BALANCE: f"{self._native_balance} {self._native_currency}",
        }

    def update(self):
        """Get the latest state of the sensor."""
        self._coinbase_data.update()
        for account in self._coinbase_data.accounts["data"]:
            if account.currency == self._currency:
                self._state = account["balance"]["amount"]
                self._native_balance = account["native_balance"]["amount"]
                self._native_currency = account["native_balance"]["currency"]
                break


class ExchangeRateSensor(SensorEntity):
    """Representation of a Coinbase.com sensor."""

    def __init__(self, coinbase_data, exchange_currency, native_currency):
        """Initialize the sensor."""
        self._coinbase_data = coinbase_data
        self.currency = exchange_currency
        self._name = f"{exchange_currency} Exchange Rate"
        self._state = round(
            1 / float(self._coinbase_data.exchange_rates.rates[self.currency]), 2
        )
        self._unit_of_measurement = native_currency

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return CURRENCY_ICONS.get(self.currency, DEFAULT_COIN_ICON)

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    def update(self):
        """Get the latest state of the sensor."""
        self._coinbase_data.update()
        self._state = round(
            1 / float(self._coinbase_data.exchange_rates.rates[self.currency]), 2
        )
