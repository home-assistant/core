"""Constants for the Fronius integration."""
from typing import Final, NamedTuple, TypedDict

from homeassistant.backports.enum import StrEnum
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import StateType

DOMAIN: Final = "fronius"

SolarNetId = str
SOLAR_NET_DISCOVERY_NEW: Final = "fronius_discovery_new"
SOLAR_NET_ID_POWER_FLOW: SolarNetId = "power_flow"
SOLAR_NET_ID_SYSTEM: SolarNetId = "system"
SOLAR_NET_RESCAN_TIMER: Final = 60


class FroniusConfigEntryData(TypedDict):
    """ConfigEntry for the Fronius integration."""

    host: str
    is_logger: bool


class FroniusDeviceInfo(NamedTuple):
    """Information about a Fronius inverter device."""

    device_info: DeviceInfo
    solar_net_id: SolarNetId
    unique_id: str


class InverterStatusCodeOption(StrEnum):
    """Status codes for Fronius inverters."""

    # these are keys for state translations - so snake_case is used
    STARTUP = "startup"
    RUNNING = "running"
    STANDBY = "standby"
    BOOTLOADING = "bootloading"
    ERROR = "error"
    IDLE = "idle"
    READY = "ready"
    SLEEPING = "sleeping"
    UNKNOWN = "unknown"
    INVALID = "invalid"


_INVERTER_STATUS_CODES: Final[dict[int, InverterStatusCodeOption]] = {
    0: InverterStatusCodeOption.STARTUP,
    1: InverterStatusCodeOption.STARTUP,
    2: InverterStatusCodeOption.STARTUP,
    3: InverterStatusCodeOption.STARTUP,
    4: InverterStatusCodeOption.STARTUP,
    5: InverterStatusCodeOption.STARTUP,
    6: InverterStatusCodeOption.STARTUP,
    7: InverterStatusCodeOption.RUNNING,
    8: InverterStatusCodeOption.STANDBY,
    9: InverterStatusCodeOption.BOOTLOADING,
    10: InverterStatusCodeOption.ERROR,
    11: InverterStatusCodeOption.IDLE,
    12: InverterStatusCodeOption.READY,
    13: InverterStatusCodeOption.SLEEPING,
    255: InverterStatusCodeOption.UNKNOWN,
}


def get_inverter_status_message(code: StateType) -> InverterStatusCodeOption:
    """Return a status message for a given status code."""
    return _INVERTER_STATUS_CODES.get(code, InverterStatusCodeOption.INVALID)  # type: ignore[arg-type]


class MeterLocationCodeOption(StrEnum):
    """Meter location codes for Fronius meters."""

    # these are keys for state translations - so snake_case is used
    FEED_IN = "feed_in"
    CONSUMPTION_PATH = "consumption_path"
    GENERATOR = "external_generator"
    SUBLOAD = "subload"


def get_meter_location_description(code: StateType) -> MeterLocationCodeOption | None:
    """Return a location_description for a given location code."""
    try:
        code = int(code)  # type: ignore[arg-type]
    except ValueError:
        return None
    match code:
        case 0:
            return MeterLocationCodeOption.FEED_IN
        case 1:
            return MeterLocationCodeOption.CONSUMPTION_PATH
        case 3:
            return MeterLocationCodeOption.GENERATOR
        case _ as _code if 256 <= _code <= 511:
            return MeterLocationCodeOption.SUBLOAD
    return None
