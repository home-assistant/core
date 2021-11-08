"""Models for the AVM FRITZ!SmartHome integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypedDict

from pyfritzhome import FritzhomeDevice


class FritzExtraAttributes(TypedDict):
    """TypedDict for sensors extra attributes."""

    device_locked: bool
    locked: bool


class ClimateExtraAttributes(FritzExtraAttributes, total=False):
    """TypedDict for climates extra attributes."""

    battery_low: bool
    battery_level: int
    holiday_mode: bool
    summer_mode: bool
    window_open: bool


@dataclass
class FritzEntityDescriptionMixinBase:
    """Bases description mixin for Fritz!Smarthome entities."""

    suitable: Callable[[FritzhomeDevice], bool]
