"""Asus Router dataclass module."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.helpers.entity import EntityDescription


@dataclass
class AREntityDescription(EntityDescription):
    """Describe Asus Router entity."""

    key_group: str | None = None
    value: Callable[[Any], Any] = lambda val: val
    extra_state_attributes: dict[str, Any] | None = None


@dataclass
class ARSensorDescription(AREntityDescription, SensorEntityDescription):
    """Describe Asus Router sensor."""
