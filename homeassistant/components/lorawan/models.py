"""Models for LoRaWAN integration discovery."""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True, kw_only=True)
class LoRaWANDiscoveryInfo:
    """Discovery information passed to device integration config flows."""
