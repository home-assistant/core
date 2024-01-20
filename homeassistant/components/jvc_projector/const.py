"""Constants for the jvc_projector integration."""

from enum import Enum

NAME = "JVC Projector"
DOMAIN = "jvc_projector"
MANUFACTURER = "JVC"
CONF_READONLY = "readonly"


class PowerState(Enum):
    """All supported power states."""

    Unknown = -1
    """Power state is not determinable."""

    Off = 0
    """Device is turned off (standby)."""

    StandBy = 1
    """Device is StandBy Mode"""

    On = 2
    """Device is turned on."""

    Cooling = 3
    """Device is cooling down before StandBy or Off"""

    Warming = 4
    """Device is powered on and warming up - Undocumented state from JVC"""

    Emergency = 5
    """Device in Emergency state"""


class Input(Enum):
    """All supported power states."""

    Unknown = -1
    """Input is not determinable."""

    HDMI1 = 1
    """Input HDMI 1"""

    HDMI2 = 2
    """Input HDMI 2"""
