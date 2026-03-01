"""The SolarLog integration models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from solarlog_cli.solarlog_connector import SolarLogConnector

    from .coordinator import (
        SolarLogBasicDataCoordinator,
        SolarLogDeviceDataCoordinator,
        SolarLogLongtimeDataCoordinator,
    )


@dataclass
class SolarlogIntegrationData:
    """Data for the solarlog integration."""

    api: SolarLogConnector
    basic_data_coordinator: SolarLogBasicDataCoordinator
    device_data_coordinator: SolarLogDeviceDataCoordinator | None = None
    longtime_data_coordinator: SolarLogLongtimeDataCoordinator | None = None
