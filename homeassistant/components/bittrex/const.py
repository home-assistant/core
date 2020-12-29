"""Constants for Bittrex."""
from datetime import timedelta

DOMAIN = "bittrex"

# Config
CONF_MARKETS = "markets"
CONF_API_SECRET = "api_secret"

# Currency
CURRENCY_ICONS = {
    "BTC": "mdi:currency-btc",
    "ETH": "mdi:currency-eth",
    "EUR": "mdi:currency-eur",
    "LTC": "mdi:litecoin",
    "USD": "mdi:currency-usd",
}

DEFAULT_COIN_ICON = "mdi:currency-usd-circle"

# Integration setup
SCAN_INTERVAL = timedelta(seconds=10)
