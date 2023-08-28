"""Constants for Camera component."""
from enum import StrEnum
from typing import Final

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
STREAM_TYPE_HLS = "hls"
STREAM_TYPE_WEB_RTC = "web_rtc"
