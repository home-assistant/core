"""Models for the BSB-Lan integration."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from bsblan import BSBLAN, Device, Info, StaticState

if TYPE_CHECKING:
    from .coordinator import BSBLanUpdateCoordinator


@dataclass
class BSBLanData:
    """BSBLan data stored in the entity."""

    coordinator: "BSBLanUpdateCoordinator"
    client: BSBLAN
    device: Device
    info: Info
    static: StaticState
