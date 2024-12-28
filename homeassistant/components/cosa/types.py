"""Type definitions for Cosa."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry


@dataclass
class CosaData:
    """Data for the Cosa integration."""


type CosaConfigEntry = ConfigEntry[CosaData]
