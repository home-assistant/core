"""Constants for the kraken integration."""

from __future__ import annotations

from typing import Dict, TypedDict

KrakenResponse = Dict[str, Dict[str, float]]


class SensorType(TypedDict):
    """SensorType class."""

    name: str
    enabled_by_default: bool


DEFAULT_SCAN_INTERVAL = 60
DEFAULT_TRACKED_ASSET_PAIR = "XBT/USD"
DISPATCH_CONFIG_UPDATED = "kraken_config_updated"

CONF_TRACKED_ASSET_PAIRS = "tracked_asset_pairs"

DOMAIN = "kraken"

SENSOR_TYPES: list[SensorType] = [
    {"name": "ask", "enabled_by_default": True},
    {"name": "ask_volume", "enabled_by_default": False},
    {"name": "bid", "enabled_by_default": True},
    {"name": "bid_volume", "enabled_by_default": False},
    {"name": "volume_today", "enabled_by_default": False},
    {"name": "volume_last_24h", "enabled_by_default": False},
    {"name": "volume_weighted_average_today", "enabled_by_default": False},
    {"name": "volume_weighted_average_last_24h", "enabled_by_default": False},
    {"name": "number_of_trades_today", "enabled_by_default": False},
    {"name": "number_of_trades_last_24h", "enabled_by_default": False},
    {"name": "last_trade_closed", "enabled_by_default": False},
    {"name": "low_today", "enabled_by_default": True},
    {"name": "low_last_24h", "enabled_by_default": False},
    {"name": "high_today", "enabled_by_default": True},
    {"name": "high_last_24h", "enabled_by_default": False},
    {"name": "opening_price_today", "enabled_by_default": False},
]
