"""Models for system monitor integration."""
from __future__ import annotations

from dataclasses import dataclass
import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntityDescription


@dataclass
class SensorData:
    """Data for a sensor."""

    argument: Any
    state: str | None
    value: Any | None
    update_time: datetime.datetime | None
    last_exception: BaseException | None


@dataclass
class SystemMonitorSensorEntityDescription(SensorEntityDescription):
    """Describes a system monitor sensor entity."""

    mandatory: bool = False
