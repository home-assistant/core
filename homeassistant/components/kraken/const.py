"""Constants for the kraken integration."""

from __future__ import annotations

from typing import TypedDict


class KrakenResponseEntry(TypedDict):
    """Dict describing a single response entry."""

    ask: tuple[float, float, float]
    bid: tuple[float, float, float]
    last_trade_closed: tuple[float, float]
    volume: tuple[float, float]
    volume_weighted_average: tuple[float, float]
    number_of_trades: tuple[int, int]
    low: tuple[float, float]
    high: tuple[float, float]
    opening_price: float


type KrakenResponse = dict[str, KrakenResponseEntry]


DEFAULT_SCAN_INTERVAL = 60
DEFAULT_TRACKED_ASSET_PAIR = "XBT/USD"
DISPATCH_CONFIG_UPDATED = "kraken_config_updated"

CONF_TRACKED_ASSET_PAIRS = "tracked_asset_pairs"

DOMAIN = "kraken"
