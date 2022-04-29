"""Utils for trafikverket_train."""
from __future__ import annotations

from datetime import time


def create_unique_id(
    from_station: str, to_station: str, depart_time: time | str | None, weekdays: list
) -> str:
    """Create unique id."""
    timestr = str(depart_time) if depart_time else ""
    return (
        f"{from_station.casefold().replace(' ', '')}-{to_station.casefold().replace(' ', '')}"
        f"-{timestr.casefold().replace(' ', '')}-{str(weekdays)}"
    )
