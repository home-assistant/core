"""Models for the A. O. Smith integration."""
from dataclasses import dataclass
from typing import Any

from py_aosmith import AOSmithAPIClient

from .coordinator import AOSmithEnergyCoordinator, AOSmithStatusCoordinator


@dataclass
class AOSmithDeviceDetails:
    """Static info about a device."""

    model: str
    name: str
    serial_number: str
    install_location: str
    firmware_version: str
    junction_id: str


def build_device_details(device: dict[str, Any]) -> AOSmithDeviceDetails:
    """Build device details from device data returned by the library."""
    return AOSmithDeviceDetails(
        model=device["model"],
        name=device["name"],
        serial_number=device["serial"],
        install_location=device["install"]["location"],
        firmware_version=device["data"]["firmwareVersion"],
        junction_id=device["junctionId"],
    )


@dataclass
class AOSmithData:
    """Data for the A. O. Smith integration."""

    device_details_list: list[AOSmithDeviceDetails]
    client: AOSmithAPIClient
    status_coordinator: AOSmithStatusCoordinator
    energy_coordinator: AOSmithEnergyCoordinator
