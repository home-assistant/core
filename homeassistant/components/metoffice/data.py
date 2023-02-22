"""Common Met Office Data class used by both sensor and entity."""


from dataclasses import dataclass

from datapoint.Forecast import Forecast
from datapoint.Site import Site
from datapoint.Timestep import Timestep


@dataclass
class MetOfficeData:
    """Data structure for MetOffice weather and forecast."""

    now: Forecast
    forecast: list[Timestep]
    site: Site
