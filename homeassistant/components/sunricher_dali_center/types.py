"""Type definitions for the DALI Center integration."""

from dataclasses import dataclass

from PySrDaliGateway import DaliGateway, DeviceType

from homeassistant.config_entries import ConfigEntry


@dataclass
class DaliCenterData:
    """Runtime data for the DALI Center integration."""

    gateway: DaliGateway
    device_data_list: list[DeviceType]


type DaliCenterConfigEntry = ConfigEntry[DaliCenterData]
