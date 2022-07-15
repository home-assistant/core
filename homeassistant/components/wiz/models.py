"""WiZ integration models."""
from dataclasses import dataclass

from pywizlight import wizlight

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


@dataclass
class WizData:
    """Data for the wiz integration."""

    coordinator: DataUpdateCoordinator
    bulb: wizlight
    scenes: list
