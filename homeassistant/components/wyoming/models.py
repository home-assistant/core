"""Models for wyoming."""
from dataclasses import dataclass

from .data import WyomingService
from .devices import SatelliteDevices


@dataclass
class DomainDataItem:
    """Domain data item."""

    service: WyomingService
    satellite_devices: SatelliteDevices
