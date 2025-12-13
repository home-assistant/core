"""Constants for the Kaleidescape integration."""

NAME = "Kaleidescape"
DOMAIN = "kaleidescape"
DEFAULT_HOST = "my-kaleidescape.local"

EVENT_TYPE_VOLUME_QUERY = f"{DOMAIN}.volume_query"
EVENT_TYPE_VOLUME_SET = f"{DOMAIN}.volume_set"
EVENT_TYPE_VOLUME_UP = f"{DOMAIN}.volume_up"
EVENT_TYPE_VOLUME_DOWN = f"{DOMAIN}.volume_down"
EVENT_TYPE_VOLUME_MUTE = f"{DOMAIN}.volume_mute"
EVENT_TYPE_USER_DEFINED_EVENT = f"{DOMAIN}.user_defined_event"

SERVICE_UPDATE_VOLUME_LEVEL = "update_volume_level"
SERVICE_ATTR_VOLUME_LEVEL = "volume_level"
SERVICE_UPDATE_VOLUME_MUTED = "update_volume_muted"
SERVICE_ATTR_VOLUME_MUTED = "is_volume_muted"
