"""Entity classes for the AEMET OpenData integration."""
from __future__ import annotations

from typing import Any

from aemet_opendata.helpers import dict_nested_value

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .weather_update_coordinator import WeatherUpdateCoordinator


class AemetEntity(CoordinatorEntity[WeatherUpdateCoordinator]):
    """Define an AEMET entity."""

    def get_aemet_value(self, keys: list[str]) -> Any:
        """Return AEMET entity value by keys."""
        return dict_nested_value(self.coordinator.data["lib"], keys)
