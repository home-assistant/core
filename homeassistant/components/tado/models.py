"""Models for use in Tado integration."""

from dataclasses import dataclass

from .coordinator import (
    TadoDataUpdateCoordinator,
    TadoMobileDeviceUpdateCoordinator,
    TadoZoneControlUpdateCoordinator,
)


@dataclass
class TadoData:
    """Class to hold Tado data."""

    coordinator: TadoDataUpdateCoordinator
    mobile_coordinator: TadoMobileDeviceUpdateCoordinator
    zone_control_coordinator: TadoZoneControlUpdateCoordinator
