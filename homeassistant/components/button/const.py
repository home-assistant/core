"""Provides the constants needed for the component."""

from enum import StrEnum
from typing import Final

import probatio

DOMAIN: Final = "button"

SERVICE_PRESS = "press"


class ButtonDeviceClass(StrEnum):
    """Device class for buttons."""

    IDENTIFY = "identify"
    RESTART = "restart"
    UPDATE = "update"


DEVICE_CLASSES_SCHEMA = probatio.All(probatio.Lower, probatio.Coerce(ButtonDeviceClass))
