"""Schedule and time period logic."""
from __future__ import annotations

import datetime

import voluptuous as vol

from .const import ATTR_END, ATTR_START


class TimePeriod:
    """Time period with start and end."""

    def __init__(self, start: str, end: str) -> None:
        """Initialize the object."""
        self.start: datetime.time = datetime.time.fromisoformat(start)
        self.end: datetime.time = datetime.time.fromisoformat(end)

    def containing(self, time: datetime.time) -> bool:
        """Check if the time is inside the period."""
        # If the period crosses the day boundary.
        if self.end <= self.start:
            return self.start <= time or time < self.end

        return self.start <= time < self.end

    def to_dict(self) -> dict[str, str]:
        """Serialize the object as a dict."""
        return {
            ATTR_START: self.start.isoformat(),
            ATTR_END: self.end.isoformat(),
        }


class Schedule:
    """List of TimePeriod."""

    def __init__(self, schedule: list[dict[str, str]]) -> None:
        """Create a list of TimePeriods representing the schedule."""
        self._schedule = [
            TimePeriod(period[ATTR_START], period[ATTR_END]) for period in schedule
        ]
        self._schedule.sort(key=lambda period: period.start)
        self._validate()

    def _validate(self) -> None:
        """Validate the schedule."""
        # Any schedule with zero or a single entry is valid.
        if len(self._schedule) <= 1:
            return

        # Check all except the last period of the schedule.
        for i in range(len(self._schedule) - 1):
            # The end should be between starts of current and next periods.
            # Note that adjusted periods are allowed.
            if (
                not self._schedule[i].start
                < self._schedule[i].end
                <= self._schedule[i + 1].start
            ):
                raise vol.Invalid("Invalid input schedule")

        # Check the last period.
        if self._schedule[-1].end <= self._schedule[-1].start:
            # If it crosses the day boundary, check overlap with 1st period.
            if self._schedule[-1].end > self._schedule[0].start:
                raise vol.Invalid("Invalid input schedule")

    def containing(self, time: datetime.time) -> bool:
        """Check if the time is inside the period."""
        for period in self._schedule:
            if period.containing(time):
                return True
        return False

    def to_list(self) -> list[dict[str, str]]:
        """Serialize the object as a list."""
        return [period.to_dict() for period in self._schedule]

    def next_update(self, date: datetime.datetime) -> datetime.datetime | None:
        """Schedule a timer for the point when the state should be changed."""
        if not self._schedule:
            return None

        time = date.time()
        today = date.date()
        prev = datetime.time()  # Midnight.

        # Get all timestamps (de-duped and sorted).
        timestamps = [period.start for period in self._schedule] + [
            period.end for period in self._schedule
        ]
        timestamps = list(set(timestamps))
        timestamps.sort()

        # Find the smallest timestamp which is bigger than time.
        for current in timestamps:
            if prev <= time < current:
                return datetime.datetime.combine(
                    today,
                    current,
                )
            prev = current

        # Time is bigger than all timestamps. Use tomorrow's 1st timestamp.
        return datetime.datetime.combine(
            today + datetime.timedelta(days=1),
            timestamps[0],
        )
