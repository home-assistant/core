"""Tests helper for Husqvarna Automower tests."""

from dataclasses import dataclass
from typing import Optional

from dacite import from_dict

from .const import AUTOMOWER_SM_SESSION_DATA


@dataclass
class System:
    """DataClass for System attributes."""

    name: str
    model: str
    serialNumber: int


@dataclass
class Battery:
    """DataClass for Battery attributes."""

    batteryPercent: int


@dataclass
class Capabilities:
    """DataClass for Capability attributes."""

    headlights: bool
    workAreas: bool
    position: bool
    stayOutZones: bool


@dataclass
class Mower:
    """DataClass for Mower values."""

    mode: str
    activity: str
    state: str
    errorCode: int
    errorCodeTimestamp: int


@dataclass
class Calendar:
    """DataClass for Calendar values."""

    start: int
    duration: int
    monday: bool
    tuesday: bool
    wednesday: bool
    thursday: bool
    friday: bool
    saturday: bool
    sunday: bool


@dataclass
class Tasks:
    """DataClass for Task values."""

    tasks: list[Calendar]


@dataclass
class Override:
    """DataClass for Override values."""

    action: str


@dataclass
class Planner:
    """DataClass for Planner values."""

    nextStartTimestamp: int
    override: Override
    restrictedReason: str


@dataclass
class Metadata:
    """DataClass for Metadata values."""

    connected: bool
    statusTimestamp: int


@dataclass
class Positions:
    """DataClass for Position values."""

    latitude: float
    longitude: float


@dataclass
class Statistics:
    """DataClass for Statistics values."""

    cuttingBladeUsageTime: Optional[int]
    numberOfChargingCycles: int
    numberOfCollisions: int
    totalChargingTime: int
    totalCuttingTime: int
    totalDriveDistance: int
    totalRunningTime: int
    totalSearchingTime: int


@dataclass
class Headlight:
    """DataClass for Headlight values."""

    mode: Optional[str]


@dataclass
class Zones:
    """DataClass for Zone values."""

    Id: str
    name: str
    enabled: bool


@dataclass
class StayOutZones:
    """DataClass for StayOutZone values."""

    dirty: bool
    zones: list[Zones]


@dataclass
class WorkAreas:
    """DataClass for WorkAreas values."""

    workAreaId: int
    name: str
    cuttingHeight: int


@dataclass
class MowerAttributes:
    """DataClass for MowerAttributes."""

    system: System
    battery: Battery
    capabilities: Capabilities
    mower: Mower
    calendar: Tasks
    planner: Planner
    metadata: Metadata
    positions: Optional[list[Positions]]
    statistics: Statistics
    cuttingHeight: Optional[int]
    headlight: Headlight
    stayOutZones: Optional[StayOutZones]
    workAreas: Optional[WorkAreas]


@dataclass
class MowerData:
    """DataClass for MowerData values."""

    type: str
    id: str
    attributes: MowerAttributes


@dataclass
class MowerList:
    """DataClass for a list of all mowers."""

    data: list[MowerData]


def make_mower_data() -> MowerList:
    """Generate a mower object."""
    mower = from_dict(data_class=MowerList, data=AUTOMOWER_SM_SESSION_DATA)
    return mower
