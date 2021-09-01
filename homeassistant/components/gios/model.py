"""Type definitions for GIOS integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import SensorEntityDescription


@dataclass
class GiosSensorEntityDescription(SensorEntityDescription):
    """Class describing GIOS sensor entities."""

    value: Callable | None = round
