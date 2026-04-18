"""Sensor Entity Description for the Growatt integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntityDescription


@dataclass(frozen=True, kw_only=True)
class GrowattSensorEntityDescription(SensorEntityDescription):
    """Describes Growatt sensor entity."""

    api_key: str
    currency: bool = False
    previous_value_drop_threshold: float | None = None
    never_resets: bool = False
