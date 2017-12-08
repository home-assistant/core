"""
Support for Coinbase sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.coinbase/
"""
from homeassistant.helpers.entity import Entity
from homeassistant.const import ATTR_ATTRIBUTION


DEPENDENCIES = ['coinbase']

DATA_COINBASE = 'coinbase_cache'

CONF_ATTRIBUTION = "Data provided by coinbase.com"
ATTR_NATIVE_BALANCE = "Balance in native currency"

BTC_ICON = 'mdi:currency-btc'
ETH_ICON = 'mdi:currency-eth'
COIN_ICON = 'mdi:coin'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Coinbase sensors."""
    if discovery_info is None:
        return False
    account = discovery_info['account']
    sensor = CoinbaseSensor(hass,
                            account['name'],
                            account['balance']['amount'],
                            account['balance']['currency'],
                            account['native_balance']['amount'],
                            account['native_balance']['currency'])

    add_devices([sensor], True)


class CoinbaseSensor(Entity):
    """Representation of a Coinbase.com sensor."""

    def __init__(self, hass, name, balance, currency, native_bal, native_cur):
        """Initialize the sensor."""
        self.hass = hass
        self._name = "Coinbase %s" % name
        self._state = balance
        self._unit_of_measurement = currency
        self._native_balance = native_bal
        self._native_currency = native_cur

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
        if self._name == "Coinbase BTC Wallet":
            return BTC_ICON
        if self._name == "Coinbase ETH Wallet":
            return ETH_ICON
        return COIN_ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            ATTR_NATIVE_BALANCE: "%s %s" % (self._native_balance,
                                            self._native_currency)
        }

    def update(self):
        """Get the latest state of the sensor."""
        self.hass.data[DATA_COINBASE].update()
        for account in self.hass.data[DATA_COINBASE].accounts['data']:
            if self._name == "Coinbase %s" % account['name']:
                self._state = account['balance']['amount']
                self._native_balance = account['native_balance']['amount']
                self._native_currency = account['native_balance']['currency']
