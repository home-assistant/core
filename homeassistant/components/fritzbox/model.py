"""Models for the AVM FRITZ!SmartHome integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypedDict

from pyfritzhome import FritzhomeDevice


class ClimateExtraAttributes(TypedDict, total=False):
    """TypedDict for climates extra attributes."""

    battery_level: int
    battery_low: bool
    holiday_mode: bool
    summer_mode: bool
    window_open: bool


@dataclass(frozen=True)
class FritzEntityDescriptionMixinBase:
    """Bases description mixin for Fritz!Smarthome entities."""

    suitable: Callable[[FritzhomeDevice], bool]
