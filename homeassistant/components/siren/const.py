"""Constants for the siren component."""

from enum import IntFlag
from functools import partial
from typing import Final

from homeassistant.helpers.deprecation import (
    DeprecatedConstantEnum,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)

DOMAIN: Final = "siren"

ATTR_TONE: Final = "tone"

ATTR_AVAILABLE_TONES: Final = "available_tones"
ATTR_DURATION: Final = "duration"
ATTR_VOLUME_LEVEL: Final = "volume_level"


class SirenEntityFeature(IntFlag):
    """Supported features of the siren entity."""

    TURN_ON = 1
    TURN_OFF = 2
    TONES = 4
    VOLUME_SET = 8
    DURATION = 16


# These constants are deprecated as of Home Assistant 2022.5
# Please use the SirenEntityFeature enum instead.
_DEPRECATED_SUPPORT_TURN_ON: Final = DeprecatedConstantEnum(
    SirenEntityFeature.TURN_ON, "2025.1"
)
_DEPRECATED_SUPPORT_TURN_OFF: Final = DeprecatedConstantEnum(
    SirenEntityFeature.TURN_OFF, "2025.1"
)
_DEPRECATED_SUPPORT_TONES: Final = DeprecatedConstantEnum(
    SirenEntityFeature.TONES, "2025.1"
)
_DEPRECATED_SUPPORT_VOLUME_SET: Final = DeprecatedConstantEnum(
    SirenEntityFeature.VOLUME_SET, "2025.1"
)
_DEPRECATED_SUPPORT_DURATION: Final = DeprecatedConstantEnum(
    SirenEntityFeature.DURATION, "2025.1"
)

# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
