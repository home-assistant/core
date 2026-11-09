"""Define the AccuWeather entity."""

from typing import Any

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION
from .coordinator import (
    AccuWeatherForecastDataUpdateCoordinator,
    AccuWeatherObservationDataUpdateCoordinator,
)


class AccuWeatherEntity[
    _CoordinatorT: AccuWeatherObservationDataUpdateCoordinator
    | AccuWeatherForecastDataUpdateCoordinator
](CoordinatorEntity[_CoordinatorT]):
    """Define an AccuWeather entity."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: _CoordinatorT, context: Any = None) -> None:
        """Initialize."""
        super().__init__(coordinator, context)

        self._attr_device_info = coordinator.device_info
