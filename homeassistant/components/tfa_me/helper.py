"""TFA.me station integration: helper.py."""

from enum import StrEnum
import re
from typing import Any

_STATION_ID_RE = re.compile(r"^[0-9A-Fa-f]{3}-[0-9A-Fa-f]{3}-[0-9A-Fa-f]{3}$")


def resolve_tfa_host(address: str) -> str:
    """Resolve user input into a usable host for TFA.me."""

    # If the address contains a valid ID scheme "XXX-XXX-XXX", assume it's a station ID and
    # build the mDNS hostname. Otherwise, assume it's an IP or hostname.

    address = address.strip()
    # Station ID ?
    if _STATION_ID_RE.fullmatch(address):
        # Yes: "XXX-XXX-XXX" -> "tfa-me-xxx-xxx-xxx.local"
        return f"tfa-me-{address.lower()}.local"

    return address


class TFAmeBatteryState(StrEnum):
    """TFA.me battery states."""

    OK = "ok"
    LOW = "low"
    CRITICAL = "critical"
    MISSING = "missing"


def battery_state(value: Any) -> TFAmeBatteryState | None:
    """Return the battery warning state."""
    return {
        0: TFAmeBatteryState.OK,
        1: TFAmeBatteryState.LOW,
        2: TFAmeBatteryState.CRITICAL,
        3: TFAmeBatteryState.MISSING,
    }.get(int(value))


class TFAmeWindDirection(StrEnum):
    """TFA.me wind directions."""

    N = "n"
    NNE = "nne"
    NE = "ne"
    ENE = "ene"
    E = "e"
    ESE = "ese"
    SE = "se"
    SSE = "sse"
    S = "s"
    SSW = "ssw"
    SW = "sw"
    WSW = "wsw"
    W = "w"
    WNW = "wnw"
    NW = "nw"
    NNW = "nnw"


def wind_direction(value: Any) -> TFAmeWindDirection | None:
    """Return the wind direction."""
    return {
        0: TFAmeWindDirection.N,
        1: TFAmeWindDirection.NNE,
        2: TFAmeWindDirection.NE,
        3: TFAmeWindDirection.ENE,
        4: TFAmeWindDirection.E,
        5: TFAmeWindDirection.ESE,
        6: TFAmeWindDirection.SE,
        7: TFAmeWindDirection.SSE,
        8: TFAmeWindDirection.S,
        9: TFAmeWindDirection.SSW,
        10: TFAmeWindDirection.SW,
        11: TFAmeWindDirection.WSW,
        12: TFAmeWindDirection.W,
        13: TFAmeWindDirection.WNW,
        14: TFAmeWindDirection.NW,
        15: TFAmeWindDirection.NNW,
    }.get(int(value))
