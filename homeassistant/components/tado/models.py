"""Models for use in Tado integration."""

from dataclasses import dataclass

from .coordinator import TadoDataUpdateCoordinator, TadoMobileDeviceUpdateCoordinator


@dataclass
class TadoData:
    """Class to hold Tado data."""

    coordinator: TadoDataUpdateCoordinator
    mobile_coordinator: TadoMobileDeviceUpdateCoordinator
