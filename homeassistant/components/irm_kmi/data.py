"""Define data classes for the IRM KMI integration."""

from dataclasses import dataclass, field

from irm_kmi_api import CurrentWeatherData, ExtendedForecast

from homeassistant.components.weather import Forecast


@dataclass
class ProcessedCoordinatorData:
    """Data exposed to entities consuming IrmKmiCoordinator data."""

    current_weather: CurrentWeatherData
    country: str
    hourly_forecast: list[Forecast] = field(default_factory=list)
    daily_forecast: list[ExtendedForecast] = field(default_factory=list)
