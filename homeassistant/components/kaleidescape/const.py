"""Constants for the Kaleidescape integration."""

NAME = "Kaleidescape"
DOMAIN = "kaleidescape"
DEFAULT_HOST = "my-kaleidescape.local"

EVENT_TYPE_VOLUME_SET_UPDATED = f"{DOMAIN}.volume_set_updated"
EVENT_TYPE_VOLUME_UP_PRESSED = f"{DOMAIN}.volume_up_pressed"
EVENT_TYPE_VOLUME_DOWN_PRESSED = f"{DOMAIN}.volume_down_pressed"
EVENT_TYPE_VOLUME_MUTE_PRESSED = f"{DOMAIN}.volume_mute_pressed"
EVENT_TYPE_USER_DEFINED_EVENT = f"{DOMAIN}.user_defined_event"

SERVICE_SEND_VOLUME_LEVEL = "send_volume_level"
SERVICE_ATTR_VOLUME_LEVEL = "level"
SERVICE_SEND_VOLUME_MUTED = "send_volume_muted"
SERVICE_ATTR_VOLUME_MUTED = "muted"
