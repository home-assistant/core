"""Entity classes for the AEMET OpenData integration."""
from __future__ import annotations

from typing import Any

from aemet_opendata.helpers import dict_nested_value

from homeassistant.components.weather import Forecast
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import WeatherUpdateCoordinator


class AemetEntity(CoordinatorEntity[WeatherUpdateCoordinator]):
    """Define an AEMET entity."""

    def get_aemet_forecast(self, forecast_mode: str) -> list[Forecast]:
        """Return AEMET entity forecast by mode."""
        return self.coordinator.data["forecast"][forecast_mode]

    def get_aemet_value(self, keys: list[str]) -> Any:
        """Return AEMET entity value by keys."""
        return dict_nested_value(self.coordinator.data["lib"], keys)
