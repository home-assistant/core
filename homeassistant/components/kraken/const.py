"""Constants for the kraken integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Dict, TypedDict

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


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


KrakenResponse = Dict[str, KrakenResponseEntry]


DEFAULT_SCAN_INTERVAL = 60
DEFAULT_TRACKED_ASSET_PAIR = "XBT/USD"
DISPATCH_CONFIG_UPDATED = "kraken_config_updated"

CONF_TRACKED_ASSET_PAIRS = "tracked_asset_pairs"

DOMAIN = "kraken"


@dataclass
class KrakenRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[DataUpdateCoordinator[KrakenResponse], str], float | int]


@dataclass
class KrakenSensorEntityDescription(SensorEntityDescription, KrakenRequiredKeysMixin):
    """Describes Kraken sensor entity."""


SENSOR_TYPES: tuple[KrakenSensorEntityDescription, ...] = (
    KrakenSensorEntityDescription(
        key="ask",
        value_fn=lambda x, y: x.data[y]["ask"][0],
    ),
    KrakenSensorEntityDescription(
        key="ask_volume",
        value_fn=lambda x, y: x.data[y]["ask"][1],
        entity_registry_enabled_default=False,
    ),
    KrakenSensorEntityDescription(
        key="bid",
        value_fn=lambda x, y: x.data[y]["bid"][0],
    ),
    KrakenSensorEntityDescription(
        key="bid_volume",
        value_fn=lambda x, y: x.data[y]["bid"][1],
        entity_registry_enabled_default=False,
    ),
    KrakenSensorEntityDescription(
        key="volume_today",
        value_fn=lambda x, y: x.data[y]["volume"][0],
        entity_registry_enabled_default=False,
    ),
    KrakenSensorEntityDescription(
        key="volume_last_24h",
        value_fn=lambda x, y: x.data[y]["volume"][1],
        entity_registry_enabled_default=False,
    ),
    KrakenSensorEntityDescription(
        key="volume_weighted_average_today",
        value_fn=lambda x, y: x.data[y]["volume_weighted_average"][0],
        entity_registry_enabled_default=False,
    ),
    KrakenSensorEntityDescription(
        key="volume_weighted_average_last_24h",
        value_fn=lambda x, y: x.data[y]["volume_weighted_average"][1],
        entity_registry_enabled_default=False,
    ),
    KrakenSensorEntityDescription(
        key="number_of_trades_today",
        value_fn=lambda x, y: x.data[y]["number_of_trades"][0],
        entity_registry_enabled_default=False,
    ),
    KrakenSensorEntityDescription(
        key="number_of_trades_last_24h",
        value_fn=lambda x, y: x.data[y]["number_of_trades"][1],
        entity_registry_enabled_default=False,
    ),
    KrakenSensorEntityDescription(
        key="last_trade_closed",
        value_fn=lambda x, y: x.data[y]["last_trade_closed"][0],
        entity_registry_enabled_default=False,
    ),
    KrakenSensorEntityDescription(
        key="low_today",
        value_fn=lambda x, y: x.data[y]["low"][0],
    ),
    KrakenSensorEntityDescription(
        key="low_last_24h",
        value_fn=lambda x, y: x.data[y]["low"][1],
        entity_registry_enabled_default=False,
    ),
    KrakenSensorEntityDescription(
        key="high_today",
        value_fn=lambda x, y: x.data[y]["high"][0],
    ),
    KrakenSensorEntityDescription(
        key="high_last_24h",
        value_fn=lambda x, y: x.data[y]["high"][1],
        entity_registry_enabled_default=False,
    ),
    KrakenSensorEntityDescription(
        key="opening_price_today",
        value_fn=lambda x, y: x.data[y]["opening_price"],
        entity_registry_enabled_default=False,
    ),
)
