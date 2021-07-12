"""Common Met Office Data class used by both sensor and entity."""

from dataclasses import dataclass

from datapoint.Day import Day
from datapoint.Forecast import Forecast
from datapoint.Site import Site


@dataclass
class MetOfficeData:
    """Data structure for MetOffice weather and forecast."""

    now: Forecast
    forecast: list[Day]
    site: Site
