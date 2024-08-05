"""WiZ integration models."""

from __future__ import annotations

from dataclasses import dataclass

from pywizlight import wizlight

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


@dataclass
class WizData:
    """Data for the wiz integration."""

    coordinator: DataUpdateCoordinator[float | None]
    bulb: wizlight
    scenes: list
