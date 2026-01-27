"""Models for the Mammotion integration."""

from dataclasses import dataclass

from pymammotion.aliyun.model.dev_by_account_response import Device
from pymammotion.homeassistant import HomeAssistantMowerApi

from .coordinator import MammotionMowerUpdateCoordinator


@dataclass
class MammotionMowerData:
    """Data for a mower information."""

    name: str
    api: HomeAssistantMowerApi
    coordinator: MammotionMowerUpdateCoordinator
    device: Device


@dataclass
class MammotionDevices:
    """Data for the Mammotion integration."""

    mowers: list[MammotionMowerData]
