"""Constants for the DirecTV integration."""
from typing import Final

DOMAIN = "directv"

# Attributes
ATTR_MEDIA_CURRENTLY_RECORDING = "media_currently_recording"
ATTR_MEDIA_RATING = "media_rating"
ATTR_MEDIA_RECORDED = "media_recorded"
ATTR_MEDIA_START_TIME = "media_start_time"
ATTR_VIA_DEVICE: Final = "via_device"

CONF_RECEIVER_ID = "receiver_id"

DEFAULT_DEVICE = "0"
DEFAULT_NAME = "DirecTV Receiver"
DEFAULT_PORT = 8080
