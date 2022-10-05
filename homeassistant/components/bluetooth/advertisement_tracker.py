"""The bluetooth integration advertisement tracker."""
from __future__ import annotations

from typing import Any

from homeassistant.core import callback

from .models import BluetoothServiceInfoBleak

ADVERTISING_TIMES_NEEDED = 16


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

    @callback
    def async_collect(self, service_info: BluetoothServiceInfoBleak) -> None:
        """Collect timings for the tracker.

        For performance reasons, it is the responsibility of the
        caller to check if the device already has an interval set in the
        tracker before calling this function.
        """
        address = service_info.address
        tracked_source = self._sources.get(address)
        current_source = service_info.source

        if tracked_source != current_source:
            # Source has changed, start tracking this source
            timings = self._timings[address] = []
            self._sources[address] = current_source
        else:
            timings = self._timings[address]

        timings.append(service_info.time)
        if len(timings) != ADVERTISING_TIMES_NEEDED:
            return

        max_time_between_advertisements = timings[1] - timings[0]
        for i in range(2, len(timings)):
            time_between_advertisements = timings[i] - timings[i - 1]
            if time_between_advertisements > max_time_between_advertisements:
                max_time_between_advertisements = time_between_advertisements

        # We now know the maximum time between advertisements
        self.intervals[address] = max_time_between_advertisements
        del self._timings[address]

    @callback
    def async_remove_address(self, address: str) -> None:
        """Remove the tracker."""
        self.intervals.pop(address, None)
        self._sources.pop(address, None)
        self._timings.pop(address, None)

    @callback
    def async_remove_source(self, source: str) -> None:
        """Remove the tracker."""
        for address in list(self._sources):
            if self._sources[address] == source:
                self.async_remove_address(address)
