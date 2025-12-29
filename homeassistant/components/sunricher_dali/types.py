"""Type definitions for the Sunricher DALI integration."""

from dataclasses import dataclass

from PySrDaliGateway import DaliGateway, Device, Scene

from homeassistant.config_entries import ConfigEntry


@dataclass
class DaliCenterData:
    """Runtime data for the Sunricher DALI integration."""

    gateway: DaliGateway
    devices: list[Device]
    scenes: list[Scene]


type DaliCenterConfigEntry = ConfigEntry[DaliCenterData]
