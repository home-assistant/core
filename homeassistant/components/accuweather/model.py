"""Type definitions for AccuWeather integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntityDescription


@dataclass
class AccuWeatherSensorDescription(SensorEntityDescription):
    """Class describing AccuWeather sensor entities."""

    unit_metric: str | None = None
    unit_imperial: str | None = None
