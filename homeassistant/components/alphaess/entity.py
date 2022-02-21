"""Parent class for AlphaESS devices."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntityDescription


@dataclass
class AlphaESSSensorDescription(SensorEntityDescription):
    """Class to describe an AlphaESS sensor."""

    native_value: Callable[
        [str | int | float], str | int | float
    ] | None = lambda val: val
