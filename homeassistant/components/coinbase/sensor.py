"""Support for Coinbase sensors."""
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity

ATTR_NATIVE_BALANCE = "Balance in native currency"

CURRENCY_ICONS = {
    "BTC": "mdi:currency-btc",
    "ETH": "mdi:currency-eth",
    "EUR": "mdi:currency-eur",
    "LTC": "mdi:litecoin",
    "USD": "mdi:currency-usd",
}

DEFAULT_COIN_ICON = "mdi:coin"

ATTRIBUTION = "Data provided by coinbase.com"

DATA_COINBASE = "coinbase_cache"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Coinbase sensors."""
    if discovery_info is None:
        return
    if "account" in discovery_info:
        account = discovery_info["account"]
        sensor = AccountSensor(
            hass.data[DATA_COINBASE], account["name"], account["balance"]["currency"]
        )
    if "exchange_currency" in discovery_info:
        sensor = ExchangeRateSensor(
            hass.data[DATA_COINBASE],
            discovery_info["exchange_currency"],
            discovery_info["native_currency"],
        )

    add_entities([sensor], True)


class AccountSensor(Entity):
    """Representation of a Coinbase.com sensor."""

    def __init__(self, coinbase_data, name, currency):
        """Initialize the sensor."""
        self._coinbase_data = coinbase_data
        self._name = f"Coinbase {name}"
        self._state = None
        self._unit_of_measurement = currency
        self._native_balance = None
        self._native_currency = None

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
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_NATIVE_BALANCE: f"{self._native_balance} {self._native_currency}",
        }

    def update(self):
        """Get the latest state of the sensor."""
        self._coinbase_data.update()
        for account in self._coinbase_data.accounts["data"]:
            if self._name == f"Coinbase {account['name']}":
                self._state = account["balance"]["amount"]
                self._native_balance = account["native_balance"]["amount"]
                self._native_currency = account["native_balance"]["currency"]


class ExchangeRateSensor(Entity):
    """Representation of a Coinbase.com sensor."""

    def __init__(self, coinbase_data, exchange_currency, native_currency):
        """Initialize the sensor."""
        self._coinbase_data = coinbase_data
        self.currency = exchange_currency
        self._name = f"{exchange_currency} Exchange Rate"
        self._state = None
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
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    def update(self):
        """Get the latest state of the sensor."""
        self._coinbase_data.update()
        rate = self._coinbase_data.exchange_rates.rates[self.currency]
        self._state = round(1 / float(rate), 2)
