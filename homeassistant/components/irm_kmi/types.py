"""Types definitions for IRM KMI integration."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .coordinator import IrmKmiCoordinator

type IrmKmiConfigEntry = ConfigEntry[IrmKmiData]


@dataclass
class IrmKmiData:
    """Data class for configuration entry runtime data."""

    coordinator: IrmKmiCoordinator
