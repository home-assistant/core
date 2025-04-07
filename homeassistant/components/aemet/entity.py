"""Entity classes for the AEMET OpenData integration."""

from __future__ import annotations

from typing import Any

from aemet_opendata.helpers import dict_nested_value

from homeassistant.components.weather import Forecast
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import WeatherUpdateCoordinator


class AemetEntity(CoordinatorEntity[WeatherUpdateCoordinator]):
    """Define an AEMET entity."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WeatherUpdateCoordinator,
        name: str,
        unique_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            name=name,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, unique_id)},
            manufacturer="AEMET",
            model="Forecast",
        )

    def get_aemet_forecast(self, forecast_mode: str) -> list[Forecast]:
        """Return AEMET entity forecast by mode."""
        return self.coordinator.data["forecast"][forecast_mode]

    def get_aemet_value(self, keys: list[str]) -> Any:
        """Return AEMET entity value by keys."""
        return dict_nested_value(self.coordinator.data["lib"], keys)
