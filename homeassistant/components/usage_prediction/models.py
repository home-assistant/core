"""Models for the usage prediction integration."""

from dataclasses import dataclass, field
from datetime import datetime

from homeassistant.util import dt as dt_util


@dataclass
class EntityUsagePredictions:
    """Prediction which entities are likely to be used in each time category."""

    morning: list[str] = field(default_factory=list)
    afternoon: list[str] = field(default_factory=list)
    evening: list[str] = field(default_factory=list)
    night: list[str] = field(default_factory=list)


@dataclass
class EntityUsageDataCache:
    """Data model for entity usage prediction."""

    predictions: EntityUsagePredictions
    timestamp: datetime = field(default_factory=dt_util.utcnow)
