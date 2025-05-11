"""Define data classes for the IRM KMI integration."""

from typing import Any

from irm_kmi_api import CurrentWeatherData, ExtendedForecast, IrmKmiApiClientHa

from homeassistant.components.weather import Forecast
from homeassistant.config_entries import ConfigEntry


class ProcessedCoordinatorData(dict[str, Any]):
    """Data class that will be exposed to the entities consuming data from an IrmKmiCoordinator."""

    current_weather: CurrentWeatherData
    hourly_forecast: list[Forecast] | None
    daily_forecast: list[ExtendedForecast] | None
    country: str


type IrmKmiConfigEntry = ConfigEntry[IrmKmiApiClientHa]
