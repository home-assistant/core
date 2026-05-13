"""Models for the EufyLife integration."""

from dataclasses import dataclass

from eufylife_ble_client import EufyLifeBLEDevice

from homeassistant.config_entries import ConfigEntry

type EufyLifeConfigEntry = ConfigEntry[EufyLifeData]


@dataclass
class EufyLifeData:
    """Data for the EufyLife integration."""

    address: str
    model: str
    client: EufyLifeBLEDevice
