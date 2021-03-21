"""Constants for Binance."""
from datetime import timedelta

DOMAIN = "binance"

# Config
CONF_API_SECRET = "api_secret"

CONF_BALANCES = "balances"
CONF_MARKETS = "markets"
CONF_OPEN_ORDERS = "open_orders"
CONF_TICKERS = "tickers"
CONF_ASSET_TICKERS = "asset_tickers"

PLATFORMS = ["sensor"]

# Currency
CURRENCY_ICONS = {
    "BTC": "mdi:currency-btc",
    "ETH": "mdi:currency-eth",
    "EUR": "mdi:currency-eur",
    "LTC": "mdi:litecoin",
    "USD": "mdi:currency-usd",
}

DEFAULT_COIN_ICON = "mdi:currency-usd"

ASSET_VALUE_CURRENCIES = {"USDT", "EUR", "BTC"}

ASSET_VALUE_BASE = "USDT"

# Integration setup
SCAN_INTERVAL = timedelta(seconds=20)
