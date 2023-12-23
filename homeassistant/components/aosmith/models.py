"""Models for the A. O. Smith integration."""
from dataclasses import dataclass

from py_aosmith import AOSmithAPIClient

from .coordinator import AOSmithEnergyCoordinator, AOSmithStatusCoordinator


@dataclass
class AOSmithData:
    """Data for the A. O. Smith integration."""

    client: AOSmithAPIClient
    status_coordinator: AOSmithStatusCoordinator
    energy_coordinator: AOSmithEnergyCoordinator
