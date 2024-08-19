"""Models for the BSB-Lan integration."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from bsblan import BSBLAN, Device, Info, StaticState
from bsblan.models import Sensor, State

if TYPE_CHECKING:
    from .coordinator import BSBLanUpdateCoordinator


@dataclass
class BSBLanCoordinatorData:
    """BSBLan data stored in the Home Assistant data object."""

    state: State
    sensor: Sensor


@dataclass
class BSBLanData:
    """BSBLan data stored in the Home Assistant data object."""

    coordinator: "BSBLanUpdateCoordinator"
    client: BSBLAN
    device: Device
    info: Info
    static: StaticState
