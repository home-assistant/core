"""Module for power off period entities."""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class PowerOffPeriod:
    """Class for power off period."""

    start: int
    end: int
    today: bool

    def to_datetime_period(self, tz_info) -> tuple[datetime, datetime]:
        """Convert to datetime period."""
        now = datetime.now().replace(tzinfo=tz_info)
        if not self.today:
            now += timedelta(days=1)

        start = now.replace(hour=self.start, minute=0, second=0, microsecond=0)
        end = now.replace(hour=self.end, minute=0, second=0, microsecond=0)
        if end < start:
            end += timedelta(days=1)
        return start, end
