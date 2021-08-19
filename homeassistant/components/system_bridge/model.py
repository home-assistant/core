"""Type definitions for System Bridge integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import SensorEntityDescription


@dataclass
class SystemBridgeSensorEntityDescription(SensorEntityDescription):
    """Class describing System Bridge sensor entities."""

    enabled_by_default: bool = False
    value: Callable = round
