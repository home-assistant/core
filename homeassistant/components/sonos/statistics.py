"""Class to track subscription event statistics."""

from __future__ import annotations

import logging

from soco.data_structures_entry import from_didl_string
from soco.events_base import Event as SonosEvent, parse_event_xml

_LOGGER = logging.getLogger(__name__)


class SonosStatistics:
    """Base class of Sonos statistics."""

    def __init__(self, zone_name: str, kind: str) -> None:
        """Initialize SonosStatistics."""
        self._stats: dict[str, dict[str, int | float]] = {}
        self._stat_type = kind
        self.zone_name = zone_name

    def report(self) -> dict:
        """Generate a report for use in diagnostics."""
        return self._stats.copy()

    def log_report(self) -> None:
        """Log statistics for this speaker."""
        _LOGGER.debug(
            "%s statistics for %s: %s",
            self._stat_type,
            self.zone_name,
            self.report(),
        )


class ActivityStatistics(SonosStatistics):
    """Representation of Sonos activity statistics."""

    def __init__(self, zone_name: str) -> None:
        """Initialize ActivityStatistics."""
        super().__init__(zone_name, "Activity")

    def activity(self, source: str, timestamp: float) -> None:
        """Track an activity occurrence."""
        activity_entry = self._stats.setdefault(source, {"count": 0})
        activity_entry["count"] += 1
        activity_entry["last_seen"] = timestamp


class EventStatistics(SonosStatistics):
    """Representation of Sonos event statistics."""

    def __init__(self, zone_name: str) -> None:
        """Initialize EventStatistics."""
        super().__init__(zone_name, "Event")

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
