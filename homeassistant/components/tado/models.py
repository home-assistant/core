"""Models for use in Tado integration."""

from dataclasses import dataclass

from .coordinator import TadoDataUpdateCoordinator


@dataclass
class TadoData:
    """Class to hold Tado data."""

    coordinator: TadoDataUpdateCoordinator
