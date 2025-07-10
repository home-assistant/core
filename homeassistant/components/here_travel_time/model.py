"""Model Classes for here_travel_time."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TypedDict

from here_routing import RoutingMode


class HERETravelTimeData(TypedDict):
    """Routing information."""

    attribution: str | None
    duration: float
    duration_in_traffic: float
    distance: float
    origin: str
    destination: str
    origin_name: str | None
    destination_name: str | None


@dataclass
class HERETravelTimeAPIParams:
    """Configuration for polling the HERE API."""

    destination: list[str]
    origin: list[str]
    travel_mode: str
    route_mode: RoutingMode
    arrival: datetime | None
    departure: datetime | None
