"""classes for the LIP protocol."""

from dataclasses import dataclass
from enum import Enum, IntEnum, StrEnum


class LIPMode(StrEnum):
    """Command modes available and parsing formats."""

    OUTPUT = "OUTPUT"
    DEVICE = "DEVICE"
    GROUP = "GROUP"
    UNKNOWN = "UNKNOWN"
    KEEPALIVE = "KEEPALIVE"
    ERROR = "ERROR"
    SYSVAR = "SYSVAR"
    MONITORING = "MONITORING"

    @classmethod
    def from_string(cls, mode_str: str) -> "LIPMode":
        """Return the Mode form the string name."""
        return cls.__members__.get(mode_str, cls.UNKNOWN)

    @property
    def parser_config(self):
        """Get the corresponding parser for the mode."""
        return PARSER_CONFIG.get(self, {})


PARSER_CONFIG = {
    LIPMode.DEVICE: {
        "component_number": (3, int),
        "action_number": (4, int),
        "value": (5, lambda x: float(x) if x is not None else 0.0),
    },
    LIPMode.OUTPUT: {
        "component_number": (None, None),
        "action_number": (3, int),
        "value": (
            4,
            lambda x: float(x) if x is not None else 0.0,
        ),  # action_number 5 (flash) doesn't have a value
    },
    LIPMode.GROUP: {
        "component_number": (None, None),
        "action_number": (3, int),
        "value": (4, int),
    },
    LIPMode.SYSVAR: {
        "component_number": (None, None),
        "action_number": (3, int),
        "value": (4, int),
    },
    LIPMode.MONITORING: {
        "component_number": (None, None),
        "action_number": (3, int),
    },
}


@dataclass
class LIPMessage:
    """Message from Lutron."""

    mode: LIPMode
    integration_id: int = 0
    component_number: int | None = None
    action_number: int = 0
    value: float = 0.0
    raw: str | None = None  # Useful for diagnostics


class LIPConnectionState(Enum):
    """Connection state."""

    NOT_CONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2


class LIPOperation(StrEnum):
    """Command operation."""

    EXECUTE = "#"
    QUERY = "?"
    RESPONSE = "~"


class LIPAction(IntEnum):
    """Class for LIP action numbers."""

    OUTPUT_LEVEL = 1  # Used for querying and setting light levels
    OUTPUT_START_RAISING = 2
    OUTPUT_START_LOWERING = 3
    OUTPUT_STOP = 4
    OUTPUT_FLASH = 5
    OUTPUT_MOTOR_JOG_RAISE = 18
    OUTPUT_MOTOR_JOG_LOWER = 19
    OUTPUT_UNDOCUMENTED_29 = (
        29  # Lutron is sending this for lights, but it's undocumented
    )
    OUTPUT_UNDOCUMENTED_30 = (
        30  # Lutron is sending this for lights, but it's undocumented
    )
    DEVICE_ENABLE = 1
    DEVICE_DISABLE = 2
    DEVICE_PRESS = 3
    DEVICE_RELEASE = 4
    DEVICE_HOLD = 5
    DEVICE_DOUBLE_TAP = 6
    DEVICE_HOLD_RELEASE = 32
    DEVICE_LED_STATE = 9  # Used for querying and setting led state
    GROUP_STATE = 3  # Used for querying a group
    SYSVAR_STATE = 1  # Used for querying a variable state


class LIPLedState(IntEnum):
    """Class for led states."""

    OFF = 0
    ON = 1
    NORMAL_FLASH = 2
    RAPID_FLASH = 3


class LIPGroupState(IntEnum):
    """Possible states of an OccupancyGroup."""

    OCCUPIED = 3
    VACANT = 4
    UNKNOWN = 255
