"""SFR Box models."""
from dataclasses import dataclass

from sfrbox_api.models import DslInfo, SystemInfo

from .coordinator import SFRDataUpdateCoordinator


@dataclass
class DomainData:
    """Domain data for SFR Box."""

    dsl: SFRDataUpdateCoordinator[DslInfo]
    system: SFRDataUpdateCoordinator[SystemInfo]
