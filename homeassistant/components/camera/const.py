"""Constants for Camera component."""
from typing import Final

DOMAIN: Final = "camera"

DATA_CAMERA_PREFS: Final = "camera_prefs"

PREF_PRELOAD_STREAM: Final = "preload_stream"

SERVICE_RECORD: Final = "record"

CONF_LOOKBACK: Final = "lookback"
CONF_DURATION: Final = "duration"

CAMERA_STREAM_SOURCE_TIMEOUT: Final = 10
CAMERA_IMAGE_TIMEOUT: Final = 10
