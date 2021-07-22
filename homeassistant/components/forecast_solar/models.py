"""Models for the Forecast.Solar integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from forecast_solar.models import Estimate


@dataclass
class ForecastSolarSensor:
    """Represents an Forecast.Solar Sensor."""

    key: str
    name: str

    device_class: str | None = None
    entity_registry_enabled_default: bool = True
    state: Callable[[Estimate], Any] | None = None
    state_class: str | None = None
    unit_of_measurement: str | None = None
