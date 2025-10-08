"""Type definitions for the Dali Center integration."""

from dataclasses import dataclass
from typing import TypedDict

from PySrDaliGateway import DaliGateway, DaliGatewayType, DeviceType

from homeassistant.config_entries import ConfigEntry


@dataclass
class DaliCenterData:
    """Runtime data for the Dali Center integration."""

    gateway: DaliGateway
    device_data_list: list[DeviceType]


class ConfigData(TypedDict, total=False):
    """Contains configuration data for the integration."""

    sn: str  # Gateway serial number
    gateway: DaliGatewayType  # Gateway object


type DaliCenterConfigEntry = ConfigEntry[DaliCenterData]
