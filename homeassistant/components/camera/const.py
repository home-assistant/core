"""Constants for Camera component."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import Camera
    from .prefs import CameraPreferences

DOMAIN: Final = "camera"
DATA_COMPONENT: HassKey[EntityComponent[Camera]] = HassKey(DOMAIN)

DATA_CAMERA_PREFS: HassKey[CameraPreferences] = HassKey("camera_prefs")

PREF_PRELOAD_STREAM: Final = "preload_stream"
PREF_ORIENTATION: Final = "orientation"

SERVICE_RECORD: Final = "record"

CONF_LOOKBACK: Final = "lookback"
CONF_DURATION: Final = "duration"

CAMERA_STREAM_SOURCE_TIMEOUT: Final = 10
CAMERA_IMAGE_TIMEOUT: Final = 10


class CameraState(StrEnum):
    """Camera entity states."""

    RECORDING = "recording"
    STREAMING = "streaming"
    IDLE = "idle"


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
