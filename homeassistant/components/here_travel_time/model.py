"""Model Classes for here_travel_time."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import TypedDict


class HERETravelTimeData(TypedDict):
    """Routing information."""

    ATTR_ATTRIBUTION: str | None
    ATTR_DURATION: float
    ATTR_DURATION_IN_TRAFFIC: float
    ATTR_DISTANCE: float
    ATTR_ORIGIN: str
    ATTR_DESTINATION: str
    ATTR_ORIGIN_NAME: str
    ATTR_DESTINATION_NAME: str


@dataclass
class HERETravelTimeConfig:
    """Configuration for HereTravelTimeDataUpdateCoordinator."""

    destination_latitude: float | None
    destination_longitude: float | None
    destination_entity_id: str | None
    origin_latitude: float | None
    origin_longitude: float | None
    origin_entity_id: str | None
    travel_mode: str
    route_mode: str
    arrival: time | None
    departure: time | None
