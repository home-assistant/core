"""Define data classes for the IRM KMI integration."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from irm_kmi_api import CurrentWeatherData

from homeassistant.components.weather import Forecast


@dataclass
class ProcessedCoordinatorData:
    """Data exposed to entities consuming IrmKmiCoordinator data."""

    current_weather: CurrentWeatherData
    country: str | None
    hourly_forecast: list[Forecast] = field(default_factory=list)
    daily_forecast: Sequence[Forecast] = field(default_factory=list)
