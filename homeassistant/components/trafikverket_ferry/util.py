"""Utils for trafikverket_ferry."""
from __future__ import annotations

from datetime import time


def create_unique_id(
    ferry_from: str, ferry_to: str, ferry_time: time | str | None, weekdays: list[str]
) -> str:
    """Create unique id."""
    return (
        f"{ferry_from.casefold().replace(' ', '')}-{ferry_to.casefold().replace(' ', '')}"
        f"-{str(ferry_time)}-{str(weekdays)}"
    )
