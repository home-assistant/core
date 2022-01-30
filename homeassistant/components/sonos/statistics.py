"""Class to track subscription event statistics."""
from __future__ import annotations

import logging

from soco.data_structures_entry import from_didl_string
from soco.events_base import Event as SonosEvent, parse_event_xml

_LOGGER = logging.getLogger(__name__)


class EventStatistics:
    """Representation of Sonos event statistics."""

    def __init__(self, zone_name: str) -> None:
        """Initialize EventStatistics."""
        self._stats = {}
        self.zone_name = zone_name

    def receive(self, event: SonosEvent) -> None:
        """Mark a received event by subscription type."""
        stats_entry = self._stats.setdefault(
            event.service.service_type, {"received": 0, "duplicates": 0, "processed": 0}
        )
        stats_entry["received"] += 1

    def duplicate(self, event: SonosEvent) -> None:
        """Mark a duplicate event by subscription type."""
        self._stats[event.service.service_type]["duplicates"] += 1

    def process(self, event: SonosEvent) -> None:
        """Mark a fully processed event by subscription type."""
        self._stats[event.service.service_type]["processed"] += 1

    def report(self) -> dict:
        """Generate a report for use in diagnostics."""
        payload = self._stats.copy()
        payload["soco:from_didl_string"] = from_didl_string.cache_info()
        payload["soco:parse_event_xml"] = parse_event_xml.cache_info()
        return payload

    def log_report(self) -> None:
        """Log event statistics for this speaker."""
        _LOGGER.debug(
            "Event statistics for %s: %s",
            self.zone_name,
            self.report(),
        )
