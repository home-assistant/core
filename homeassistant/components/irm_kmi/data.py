"""Define data classes for the IRM KMI integration."""

from dataclasses import dataclass, field

from irm_kmi_api import CurrentWeatherData, ExtendedForecast

from homeassistant.components.weather import Forecast


@dataclass
class ProcessedCoordinatorData:
    """Dataclass that will be exposed to the entities consuming data from an IrmKmiCoordinator."""

    current_weather: CurrentWeatherData
    country: str
    hourly_forecast: list[Forecast] = field(default_factory=list)
    daily_forecast: list[ExtendedForecast] = field(default_factory=list)

    def get(self, key, default=None):
        """Return the value for key if key is in the ProcessedCoordinatorData, else default."""
        return getattr(self, key, default)
