"""Type definitions for Airly integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import SensorEntityDescription


@dataclass
class AirlySensorEntityDescription(SensorEntityDescription):
    """Class describing Airly sensor entities."""

    value: Callable = round
