"""SFR Box models."""
from dataclasses import dataclass

from sfrbox_api.bridge import SFRBox
from sfrbox_api.models import DslInfo, FtthInfo, SystemInfo, WanInfo

from .coordinator import SFRDataUpdateCoordinator


@dataclass
class DomainData:
    """Domain data for SFR Box."""

    box: SFRBox
    dsl: SFRDataUpdateCoordinator[DslInfo]
    ftth: SFRDataUpdateCoordinator[FtthInfo]
    system: SFRDataUpdateCoordinator[SystemInfo]
    wan: SFRDataUpdateCoordinator[WanInfo]
