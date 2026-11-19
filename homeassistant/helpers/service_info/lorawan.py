"""LoRaWAN discovery data."""

from dataclasses import dataclass

from homeassistant.data_entry_flow import BaseServiceInfo


@dataclass(slots=True)
class LoRaWANDiscoveryInfo(BaseServiceInfo):
    """Discovery information passed to device integration config flows."""
