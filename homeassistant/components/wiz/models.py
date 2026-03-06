"""WiZ integration models."""

from __future__ import annotations

from dataclasses import dataclass

from pywizlight import wizlight

from .coordinator import WizCoordinator


@dataclass
class WizData:
    """Data for the wiz integration."""

    coordinator: WizCoordinator
    bulb: wizlight
    scenes: list
