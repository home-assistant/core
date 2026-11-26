"""Constants for the reCamera Pro integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "recamera_pro"
MANUFACTURER = "Seeed Studio"
CONFIG_ENTRY_VERSION = 1

PLATFORMS = (Platform.CAMERA,)

CONF_DEVICE_ID = "device_id"
CONF_DISCOVERY_CANDIDATES = "discovery_candidates"
CONF_DISCOVERY_ID = "discovery_id"
CONF_HW_VERSION = "hw_version"
CONF_MAC_ADDRESS = "mac_address"
CONF_MODEL = "model"
CONF_SERIAL_NUMBER = "serial_number"
CONF_SW_VERSION = "sw_version"

CONF_TRACKED_CLASSES = "tracked_classes"
CONF_VISUAL_CONFIDENCE = "visual_min_confidence"
CONF_VISUAL_CONFIRM = "visual_confirm_seconds"
CONF_AUDIO_CONFIDENCE = "audio_min_confidence"
CONF_CLASS_STALE_SECONDS = "class_stale_seconds"
CONF_VISUAL_COOLDOWN = "visual_cooldown_seconds"
CONF_AUDIO_COOLDOWN = "audio_cooldown_seconds"
CONF_LANGUAGE = "language"

DEFAULT_TRACKED_CLASSES: tuple[str, ...] = ()
DEFAULT_VISUAL_CONFIDENCE = 0.5
DEFAULT_VISUAL_CONFIRM = 0.0
DEFAULT_AUDIO_CONFIDENCE = 0.8
DEFAULT_CLASS_STALE_SECONDS = 8.0
DEFAULT_VISUAL_COOLDOWN = 2.0
DEFAULT_AUDIO_COOLDOWN = 5.0
DEFAULT_LANGUAGE = "auto"

SERVICE_TYPE = "_recamera._tcp.local."
DIRECT_RESULTS_WS_PATH = "/ws/ai/results/v2"
MOTION_APP_ID = "motion-detect"
DIRECT_RESULTS_SUBSCRIBE = {
    "type": "subscribe",
    "view": "raw",
    "sources": ["builtin", "acousticslab", MOTION_APP_ID],
    "types": ["frame", "event", "status"],
}

AUDIO_SOURCE_ID = "acousticslab"
SOURCE_AVAILABLE = "available"
SOURCE_UNKNOWN = "unknown"
SOURCE_UNAVAILABLE = "unavailable"

EVENT_FIRMWARE_UPDATE_COMPLETED = f"{DOMAIN}_firmware_update_completed"

UPDATE_INTERVAL = timedelta(seconds=60)
SOURCE_OFFLINE_SECONDS = 30.0
EVENT_HISTORY_LIMIT = 64
STORAGE_VERSION = 1

WEBSOCKET_RETRY_MIN = 2
WEBSOCKET_RETRY_MAX = 30
MOTION_TRANSITION_TIMEOUT_SECONDS = 30.0

OTA_RELEASE_URL = "https://github.com/Seeed-Studio/reCamera-Pro-OTA"
OTA_RELEASE_PAGE_URL = f"{OTA_RELEASE_URL}/releases"
OTA_RELEASE_LATEST_API_URL = (
    "https://api.github.com/repos/Seeed-Studio/reCamera-Pro-OTA/releases/latest"
)
OTA_CHECK_INTERVAL_SECONDS = 6 * 60 * 60
OTA_DOWNLOAD_TIMEOUT_SECONDS = 30 * 60
OTA_POLL_INTERVAL_SECONDS = 2.0
FIRMWARE_REBOOT_TIMEOUT_SECONDS = 10 * 60
FIRMWARE_RECONNECT_POLL_SECONDS = 3.0
