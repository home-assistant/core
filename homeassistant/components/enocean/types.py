"""Types for the EnOcean integration."""

from dataclasses import dataclass

from enocean_async import Gateway

from homeassistant.config_entries import ConfigEntry


@dataclass(frozen=True)
class EnOceanConfigEntryData:
    """EnOcean data class."""

    gateway: Gateway


type EnOceanConfigEntry = ConfigEntry[EnOceanConfigEntryData]
