"""Domain-model enums and device-name lookup for the BLANCO integration.

Defines the HA-side domain types used across integration modules:
device types, device names, and time ranges.  API-side enums (BlancoErrorType,
BlancoActionType, BlancoWaterType) live in blanco_smart_home_api_client.models.
"""

from __future__ import annotations

from enum import IntEnum


class BlancoDeviceType(IntEnum):
    """Device types returned by the /auth/token endpoint."""

    UNDEF = 0
    """Unknown or unsupported device type."""
    SODA = 1
    """EVOL-S PRO — sparkling/still water dispenser with CO₂."""
    AIO = 2
    """CHOICE.ALL — all-in-one dispenser with hot, cold, and sparkling water."""
    SODA2 = 3
    """CHOICE.Soda — sparkling/still water dispenser."""
    FILTER = 4
    """CHOICE.Filter — filtered cold water dispenser."""
    HOT = 5
    """CHOICE.Hot — hot water dispenser."""
    SELECT = 6
    """SELECT II — multi-function water dispenser."""
    FLEXON = 7
    """FLEXON II — flexible water dispenser."""
    SEPURA = 8
    """SEPURA — water dispenser with filtration."""
    AQUA = 9
    """AQUA — filtration unit with volume- and time-based filter tracking."""
    BIOSORT = 10
    """BIOSORT — biological filtration system."""


BLANCO_DEVICE_NAMES: dict[BlancoDeviceType, str] = {
    BlancoDeviceType.UNDEF: "UNKNOWN",
    BlancoDeviceType.SODA: "EVOL-S PRO",
    BlancoDeviceType.AIO: "CHOICE.ALL",
    BlancoDeviceType.SODA2: "CHOICE.Soda",
    BlancoDeviceType.FILTER: "CHOICE.Filter",
    BlancoDeviceType.HOT: "CHOICE.Hot",
    BlancoDeviceType.SELECT: "SELECT II",
    BlancoDeviceType.FLEXON: "FLEXON II",
    BlancoDeviceType.SEPURA: "SEPURA",
    BlancoDeviceType.AQUA: "AQUA",
    BlancoDeviceType.BIOSORT: "BIOSORT",
}
"""Maps each BlancoDeviceType to its human-readable marketing name, used in device_info."""


class BlancoTimeRange(IntEnum):
    """Time range used to group or filter consumption and event data."""

    UNDEF = 0
    """Unknown or unspecified time range — used as a safe fallback."""
    DAY = 1
    """Aggregation or filter covering a single day."""
    WEEK = 2
    """Aggregation or filter covering a calendar week."""
    MONTH = 3
    """Aggregation or filter covering a calendar month."""
    YEAR = 4
    """Aggregation or filter covering a calendar year."""
