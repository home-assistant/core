"""Models for wyoming."""

from dataclasses import dataclass

from .data import WyomingService
from .devices import SatelliteDevice


@dataclass
class DomainDataItem:
    """Domain data item."""

    service: WyomingService
    device: SatelliteDevice | None = None
