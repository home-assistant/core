"""Types definitions for IRM KMI integration."""

from dataclasses import dataclass

from irm_kmi_api import IrmKmiApiClientHa

from homeassistant.config_entries import ConfigEntry

from .coordinator import IrmKmiCoordinator

type IrmKmiConfigEntry = ConfigEntry[IrmKmiData]


@dataclass
class IrmKmiData:
    """Data class for configuration entry runtime data."""

    api_client: IrmKmiApiClientHa
    coordinator: IrmKmiCoordinator
