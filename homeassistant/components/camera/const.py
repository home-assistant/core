"""Constants for Camera component."""
from enum import StrEnum
from functools import partial
from typing import Final

from homeassistant.helpers.deprecation import (
    DeprecatedConstantEnum,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)

DOMAIN: Final = "camera"

DATA_CAMERA_PREFS: Final = "camera_prefs"
DATA_RTSP_TO_WEB_RTC: Final = "rtsp_to_web_rtc"

PREF_PRELOAD_STREAM: Final = "preload_stream"
PREF_ORIENTATION: Final = "orientation"

SERVICE_RECORD: Final = "record"

CONF_LOOKBACK: Final = "lookback"
CONF_DURATION: Final = "duration"

CAMERA_STREAM_SOURCE_TIMEOUT: Final = 10
CAMERA_IMAGE_TIMEOUT: Final = 10


class StreamType(StrEnum):
    """Camera stream type.

    A camera that supports CAMERA_SUPPORT_STREAM may have a single stream
    type which is used to inform the frontend which player to use.
    Streams with RTSP sources typically use the stream component which uses
    HLS for display. WebRTC streams use the home assistant core for a signal
    path to initiate a stream, but the stream itself is between the client and
    device.
    """

    HLS = "hls"
    WEB_RTC = "web_rtc"


# These constants are deprecated as of Home Assistant 2022.5
# Please use the StreamType enum instead.
_DEPRECATED_STREAM_TYPE_HLS = DeprecatedConstantEnum(StreamType.HLS, "2025.1")
_DEPRECATED_STREAM_TYPE_WEB_RTC = DeprecatedConstantEnum(StreamType.WEB_RTC, "2025.1")


# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
