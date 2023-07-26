"""Models for PEGELONLINE."""

from typing import TypedDict

from aiopegelonline import CurrentMeasurement


class PegelOnlineData(TypedDict):
    """TypedDict for PEGELONLINE Coordinator Data."""

    water_level: CurrentMeasurement
