"""SFR Box models."""

from dataclasses import dataclass

from sfrbox_api.bridge import SFRBox
from sfrbox_api.models import DslInfo, FtthInfo, SystemInfo, WanInfo

from homeassistant.config_entries import ConfigEntry

from .coordinator import SFRDataUpdateCoordinator

type SFRConfigEntry = ConfigEntry[SFRRuntimeData]


@dataclass
class SFRRuntimeData:
    """Runtime data for SFR Box."""

    box: SFRBox
    dsl: SFRDataUpdateCoordinator[DslInfo]
    ftth: SFRDataUpdateCoordinator[FtthInfo]
    system: SFRDataUpdateCoordinator[SystemInfo]
    wan: SFRDataUpdateCoordinator[WanInfo]
