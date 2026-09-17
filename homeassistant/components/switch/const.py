"""Constants for the Switch integration."""

from enum import StrEnum
from typing import Final

import probatio

DOMAIN: Final = "switch"


class SwitchDeviceClass(StrEnum):
    """Device class for switches."""

    OUTLET = "outlet"
    SWITCH = "switch"


DEVICE_CLASSES_SCHEMA = probatio.All(probatio.Lower, probatio.Coerce(SwitchDeviceClass))
