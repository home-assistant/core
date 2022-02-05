"""WiZ integration models."""
from dataclasses import dataclass

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pywizlight import wizlight


@dataclass
class WizData:
    """Data for the wiz integration."""

    coordinator: DataUpdateCoordinator
    bulb: wizlight
    scenes: list
