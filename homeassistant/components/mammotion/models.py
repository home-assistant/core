"""Models for the Mammotion integration."""

from dataclasses import dataclass

from pymammotion.aliyun.model.dev_by_account_response import Device
from pymammotion.data.model.device_limits import DeviceLimits
from pymammotion.homeassistant import HomeAssistantMowerApi

from .coordinator import MammotionReportUpdateCoordinator


@dataclass
class MammotionMowerData:
    """Data for a mower information."""

    name: str
    api: HomeAssistantMowerApi
    reporting_coordinator: MammotionReportUpdateCoordinator
    device_limits: DeviceLimits
    device: Device


@dataclass
class MammotionDevices:
    """Data for the Mammotion integration."""

    mowers: list[MammotionMowerData]
