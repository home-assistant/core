"""Type definitions for the DALI Center integration."""

from dataclasses import dataclass

from PySrDaliGateway import DaliGateway, Device

from homeassistant.config_entries import ConfigEntry


@dataclass
class DaliCenterData:
    """Runtime data for the DALI Center integration."""

    gateway: DaliGateway
    devices: list[Device]


type DaliCenterConfigEntry = ConfigEntry[DaliCenterData]
