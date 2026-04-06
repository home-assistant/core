"""Custom types for Touchline."""

from __future__ import annotations

from dataclasses import dataclass

from pytouchline_extended import PyTouchline

from homeassistant.config_entries import ConfigEntry

type TouchlineConfigEntry = ConfigEntry[TouchlineData]


@dataclass
class TouchlineData:
    """Runtime data for the Touchline integration."""

    touchline: PyTouchline
    number_of_devices: int
