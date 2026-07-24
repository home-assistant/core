"""Models for wyoming."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .data import WyomingService
from .devices import SatelliteDevice


@dataclass
class DomainDataItem:
    """Domain data item."""

    service: WyomingService
    device: SatelliteDevice | None = None


type WyomingConfigEntry = ConfigEntry[DomainDataItem]
