"""Models for wyoming."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

from .data import WyomingService
from .devices import SatelliteDevice

if TYPE_CHECKING:
    from .assist_satellite import WyomingAssistSatellite


@dataclass
class DomainDataItem:
    """Domain data item."""

    service: WyomingService
    device: SatelliteDevice | None = None
    satellite: WyomingAssistSatellite | None = None


type WyomingConfigEntry = ConfigEntry[DomainDataItem]
