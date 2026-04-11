"""Models for use in Tado integration."""

from dataclasses import dataclass

from .coordinator import TadoDataUpdateCoordinator, TadoZoneControlUpdateCoordinator


@dataclass
class TadoData:
    """Class to hold Tado data."""

    coordinator: TadoDataUpdateCoordinator
    zone_control_coordinator: TadoZoneControlUpdateCoordinator
