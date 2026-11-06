"""Constants for the System Bridge integration."""

from typing import Final

from systembridgeconnector.models.modules import Module

DOMAIN = "system_bridge"

MODULES: Final[list[Module]] = [
    Module.BATTERY,
    Module.CPU,
    Module.DISKS,
    Module.DISPLAYS,
    Module.GPUS,
    Module.MEDIA,
    Module.MEMORY,
    Module.NETWORKS,
    Module.PROCESSES,
    Module.SYSTEM,
]

# Backends before 5.16.0 never answer a request for the audio module
AUDIO_MIN_VERSION: Final = (5, 16, 0)

# Backends before 5.23.0 list players without their controls or details
PLAYER_DETAILS_MIN_VERSION: Final = (5, 23, 0)

AUDIO_OUTPUT: Final = "output"
AUDIO_INPUT: Final = "input"

DATA_WAIT_TIMEOUT: Final[int] = 20

GET_DATA_WAIT_TIMEOUT: Final[int] = 15
