"""Constants for the kraken integration."""
from __future__ import annotations

from typing import Dict

from homeassistant.components.sensor import SensorEntityDescription

KrakenResponse = Dict[str, Dict[str, float]]


DEFAULT_SCAN_INTERVAL = 60
DEFAULT_TRACKED_ASSET_PAIR = "XBT/USD"
DISPATCH_CONFIG_UPDATED = "kraken_config_updated"

CONF_TRACKED_ASSET_PAIRS = "tracked_asset_pairs"

DOMAIN = "kraken"

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="ask",
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="ask_volume",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="bid",
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="bid_volume",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="volume_today",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="volume_last_24h",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="volume_weighted_average_today",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="volume_weighted_average_last_24h",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="number_of_trades_today",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="number_of_trades_last_24h",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="last_trade_closed",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="low_today",
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="low_last_24h",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="high_today",
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="high_last_24h",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="opening_price_today",
        entity_registry_enabled_default=False,
    ),
)
