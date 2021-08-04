"""Constants for the Uptime Robot integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from logging import Logger, getLogger
from typing import Final

LOGGER: Logger = getLogger(__package__)

COORDINATOR_UPDATE_INTERVAL: timedelta = timedelta(seconds=60)

DOMAIN: Final = "uptimerobot"
PLATFORMS: Final = ["binary_sensor"]

CONNECTION_ERROR: Final = "Error connecting to the Uptime Robot API"

ATTRIBUTION: Final = "Data provided by Uptime Robot"

ATTR_TARGET: Final = "target"

API_ATTR_STAT: Final = "stat"
API_ATTR_OK: Final = "ok"
API_ATTR_MONITORS: Final = "monitors"


class MonitorType(Enum):
    """Monitors type."""

    HTTP = 1
    keyword = 2
    ping = 3


@dataclass
class MonitorData:
    """Dataclass for monitors."""

    id: int
    status: int
    url: str
    name: str
    type: MonitorType

    @staticmethod
    def from_dict(monitor: dict) -> MonitorData:
        """Create a new monitor from a dict."""
        return MonitorData(
            id=monitor["id"],
            status=monitor["status"],
            url=monitor["url"],
            name=monitor["friendly_name"],
            type=MonitorType(monitor["type"]),
        )
