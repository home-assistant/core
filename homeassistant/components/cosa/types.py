"""Type definitions for the Cosa integration."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .coordinator import CosaCoordinator


@dataclass
class CosaData:
    """Runtime data for the Cosa integration."""

    coordinators: dict[str, CosaCoordinator]


type CosaConfigEntry = ConfigEntry[CosaData]
