"""The bluetooth integration advertisement tracker."""
from __future__ import annotations

from typing import Any

from homeassistant.core import callback

from .models import BluetoothServiceInfoBleak

ADVERTISING_TIMES_NEEDED = 10


class AdvertisementTracker:
    """Tracker to determine the interval that a device is advertising."""

    def __init__(self) -> None:
        """Initialize the tracker."""
        self.intervals: dict[str, float] = {}
        self._sources: dict[str, str] = {}
        self._timings: dict[str, list[float]] = {}

    @callback
    def async_diagnostics(self) -> dict[str, dict[str, Any]]:
        """Return diagnostics."""
        return {
            "intervals": self.intervals,
            "sources": self._sources,
            "timings": self._timings,
        }

    def collect(self, service_info: BluetoothServiceInfoBleak) -> None:
        """Collect timings for the tracker."""
        address = service_info.address
        assert (
            address not in self.intervals
        ), f"Implementor error: interval already exist for {address}"

        if tracked_source := self._sources.get(address):
            # Source has changed, start tracking again
            if tracked_source != service_info.source:
                self._timings[address] = []

        timings = self._timings.setdefault(address, [])
        timings.append(service_info.time)
        if len(timings) != ADVERTISING_TIMES_NEEDED:
            return

        max_time_between_advertisements = timings[1] - timings[0]
        for i, timing in enumerate(timings, 2):
            time_between_advertisements = timing - timings[i - 1]
            if time_between_advertisements > max_time_between_advertisements:
                max_time_between_advertisements = time_between_advertisements

        # We now know the maximum time between advertisements
        self.intervals[address] = max_time_between_advertisements
        del self._timings[address]

    def remove_address(self, address: str) -> None:
        """Remove the tracker."""
        self.intervals.pop(address, None)
        self._sources.pop(address, None)
        self._timings.pop(address, None)

    def remove_source(self, source: str) -> None:
        """Remove the tracker."""
        for address in list(self._sources):
            if self._sources[address] == source:
                self.remove_address(address)
