"""Models for wyoming."""

from dataclasses import dataclass

from .data import WyomingService
from .satellite import WyomingSatellite


@dataclass
class DomainDataItem:
    """Domain data item."""

    service: WyomingService
    satellite: WyomingSatellite | None = None
