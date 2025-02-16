from dataclasses import dataclass

from pymammotion.aliyun.model.dev_by_account_response import Device
from pymammotion.data.model.device_limits import DeviceLimits
from pymammotion.mammotion.devices.mammotion import Mammotion

from . import (
    MammotionDeviceVersionUpdateCoordinator,
    MammotionMaintenanceUpdateCoordinator,
)
from .coordinator import MammotionReportUpdateCoordinator


@dataclass
class MammotionMowerData:
    """Data for a mower information."""

    name: str
    api: Mammotion
    maintenance_coordinator: MammotionMaintenanceUpdateCoordinator
    reporting_coordinator: MammotionReportUpdateCoordinator
    version_coordinator: MammotionDeviceVersionUpdateCoordinator
    device_limits: DeviceLimits
    device: Device


@dataclass
class MammotionDevices:
    """Data for the Mammotion integration."""

    mowers: list[MammotionMowerData]
