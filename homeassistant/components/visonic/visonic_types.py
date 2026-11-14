"""Global Visonic Types."""

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import Any, Self, override

from homeassistant.components.alarm_control_panel import AlarmControlPanelState


class VisonicStrEnum(StrEnum):
    """Base class for string enumerations for common functions."""

    @override
    def title(self) -> str:
        """Make a title case with no underscores."""
        return self.value.replace("_", " ").title()

    @classmethod
    def from_title(cls, text: str) -> Self:
        """String to main class. Do the opposite of title above."""
        normalized = text.strip().lower().replace(" ", "_")
        return cls(normalized)


########################################################################################################################################
#
#  DeviceType
#    ETHERNET         A direct TCP connection is made to a device in the panel.
#                     This device must be a TCP Server that translates data to/from the panel
#                          An ESPHome device can be configured do to this
#    SERIAL           A direct serial connection is made to a device in the panel.
#    CLOUD            A REST API connection is made to an external Visonic Server (with login details and user code)
#                          The Visonic Go App can be used in conjunction with this
#                     The panel must be PowerMaster with a Powerlink 3.1 hardware module
#                     As this is a polled mechanism (and not a direct connection to the panel) this has delayed updates
#
########################################################################################################################################
class DeviceType(VisonicStrEnum):
    """Device Type."""

    ETHERNET = "ethernet"
    SERIAL = "serial"
    CLOUD = "cloud_server"


class VisonicIntEnum(IntEnum):
    """Base Int enum for Visonic devices."""

    # This will be extended to include access functions


# The set of commands that can be used to arm and disarm the panel
class AlarmPanelCommand(VisonicIntEnum):
    """Enumeration of commands to arm and disarm the panel."""

    # Include all case variations for the panel_command HA service
    #   The values used in the code have to be first
    DISARM = 1
    ARM_HOME = 2
    ARM_AWAY = 3
    ARM_HOME_INSTANT = 4
    ARM_AWAY_INSTANT = 5


# The result of using the set of commands
class AlarmCommandStatus(VisonicIntEnum):
    """Enumeration of command execution results."""

    SUCCESS = 1
    FAIL_DOWNLOAD_IN_PROGRESS = 2
    FAIL_INVALID_CODE = 3
    FAIL_USER_CONFIG_PREVENTED = 4
    FAIL_INVALID_STATE = 5
    FAIL_SWITCH_PROBLEM = 6
    FAIL_PANEL_CONFIG_PREVENTED = 7
    FAIL_ABSTRACT_CLASS_NOT_IMPLEMENTED = 8
    FAIL_PANEL_NO_CONNECTION = 9
    FAIL_ENTITY_INCORRECT = 10
    FAIL_INVALID_RETURN = 11
    FAIL_RECOVERY_IN_PROGRESS = 12

    # Make values not in the libraries high values
    FAIL_INVALID_PROCESS_TOKEN = 200


class AlarmPanelStatus(VisonicIntEnum):
    """Panel status values compatible with the direct library."""

    UNKNOWN = 1
    DISARMED = 2
    ARMING_HOME = 3
    ARMING_AWAY = 4
    ENTRY_DELAY = 5
    ARMED_HOME = 6
    ARMED_AWAY = 7
    ARMED_HOME_BYPASS = 8
    ARMED_AWAY_BYPASS = 9
    ARMED_HOME_INSTANT = 10
    ARMED_AWAY_INSTANT = 11
    ENTRY_DELAY_INSTANT = 12
    USER_TEST = 13
    DOWNLOADING = 14
    INSTALLER = 15
    TRIGGERED = 20  # The panel does not report this directly, it is derived in the code


# This class represents the reasons that could trigger an alarm
#     These could be set even if the siren is not sounding, depending on the panel settings
class TriggerAlarmType(VisonicIntEnum):
    """Enumeration of alarm types that can trigger an alarm condition."""

    UNKNOWN = 1
    NONE = 2
    INTRUDER = 3
    TAMPER = 4
    PANIC = 5
    FIRE = 6
    EMERGENCY = 7
    GAS = 8
    FLOOD = 9
    SWITCH = 10


@dataclass(frozen=True)
class PanelStateData:
    """Return class for update."""

    connected: bool = False
    achieved_powerlink: bool = False
    alarm_state: AlarmControlPanelState | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


##############################################################################################################################################################################################################################################
##########################  Panel Event coordinator to manage A5, B0.24 and A7 panel state and event data ####################################################################################################################################
##############################################################################################################################################################################################################################################


class PanelCondition(VisonicIntEnum):
    """Panel condition codes for event handling."""

    # These match AlCondition (pyvisonic library) for easy cast.
    PUSH_CHANGE = 1
    ZONE_UPDATE = 2
    PANEL_UPDATE = 3
    PANEL_RESET = 4
    PIN_REJECTED = 5
    DOWNLOAD_SUCCESS = 6
    DOWNLOAD_TIMEOUT = 7
    WATCHDOG_TIMEOUT_GIVINGUP = 8
    WATCHDOG_TIMEOUT_RETRYING = 9
    NO_DATA_FROM_PANEL = 10
    COMMAND_REJECTED = 11
    STARTUP_SUCCESS = 12
    IMAGE_UPDATE = 13
    GSM_MODULE_INSTALLED = 14
    # These start at 100 to ensure uniqueness when mixing with AlCondition (pyvisonic library).
    CHECK_ARM_DISARM_COMMAND = 100
    CHECK_BYPASS_COMMAND = 101
    CHECK_EVENT_LOG_COMMAND = 102
    CHECK_SWITCH_COMMAND = 103
    CONNECTION = 104
    PANEL_LOG_COMPLETE = 105
    PANEL_LOG_ENTRY = 106
    NO_PANEL_CONDITION_DEFINED = 1000


@dataclass(slots=True)
class CommandResult:
    """Client command result."""

    status: AlarmCommandStatus
