"""Type definitions for System Bridge integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.sensor import SensorEntityDescription


@dataclass
class SystemBridgeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing System Bridge binary sensor entities."""

    value: Callable = round


@dataclass
class SystemBridgeSensorEntityDescription(SensorEntityDescription):
    """Class describing System Bridge sensor entities."""

    value: Callable = round
