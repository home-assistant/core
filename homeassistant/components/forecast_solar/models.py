"""Models for the Forecast.Solar integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from forecast_solar.models import Estimate

from homeassistant.components.sensor import SensorEntityDescription


@dataclass
class ForecastSolarSensorEntityDescription(SensorEntityDescription):
    """Describes a Forecast.Solar Sensor."""

    state: Callable[[Estimate], Any] | None = None
