"""Models for pegel_online."""

from typing import TypedDict

from aiopegelonline import CurrentMeasurement


class PegelOnlineData(TypedDict):
    """TypedDict for pegel_online Coordinator Data."""

    current_measurement: CurrentMeasurement
