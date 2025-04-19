"""Constants for the System Bridge integration."""

from typing import Final

from systembridgemodels.modules import Module

DOMAIN = "system_bridge"

MODULES: Final[list[Module]] = [
    Module.BATTERY,
    Module.CPU,
    Module.DISKS,
    Module.DISPLAYS,
    Module.GPUS,
    Module.MEDIA,
    Module.MEMORY,
    Module.PROCESSES,
    Module.SYSTEM,
]

DATA_WAIT_TIMEOUT: Final[int] = 10
