"""Constants for the Novy Cooker Hood integration."""

from __future__ import annotations

from typing import Final

from rf_protocols import ModulationType

DOMAIN: Final = "novy_cooker_hood"

CONF_TRANSMITTER: Final = "transmitter"
CONF_CODE: Final = "code"

CODE_MIN: Final = 1
CODE_MAX: Final = 10
DEFAULT_CODE: Final = 1

FREQUENCY: Final = 433_920_000
MODULATION: Final = ModulationType.OOK

SPEED_COUNT: Final = 4
