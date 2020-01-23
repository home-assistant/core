"""Constants for the kraken integration."""

DEFAULT_SCAN_INTERVAL = 60
DEFAULT_TRACKED_ASSET_PAIR = "XBT/USD"
DISPATCH_CONFIG_UPDATED = "kraken_config_updated"

CONF_TRACKED_ASSET_PAIRS = "tracked_asset_pairs"

DOMAIN = "kraken"

SENSOR_TYPES = [
    "ask",
    "ask_volume",
    "bid",
    "bid_volume",
    "volume_today",
    "volume_last_24h",
    "volume_weighted_average_today",
    "volume_weighted_average_last_24h",
    "number_of_trades_today",
    "number_of_trades_last_24h",
    "last_trade_closed",
    "low_today",
    "low_last_24h",
    "high_today",
    "high_last_24h",
    "opening_price_today",
]
