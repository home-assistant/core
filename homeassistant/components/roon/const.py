"""Constants for Roon Component."""

AUTHENTICATE_TIMEOUT = 5

DOMAIN = "roon"

CONF_ROON_ID = "roon_server_id"
CONF_ROON_NAME = "roon_server_name"
CONF_ENABLE_VOLUME_HOOKS = "roon_volume_hooks"

CONF_VOLUME_HOOK_ON = "volume_hook_on"
CONF_VOLUME_HOOK_OFF = "volume_hook_off"

DATA_CONFIGS = "roon_configs"

DEFAULT_NAME = "Roon Labs Music Player"

ROON_APPINFO = {
    "extension_id": "home_assistant",
    "display_name": "Home Assistant",
    "display_version": "1.0.1",
    "publisher": "home_assistant",
    "email": "home_assistant@users.noreply.github.com",
    "website": "https://www.home-assistant.io/",
}

ROON_EVENT = "roon_event"

ROON_EVENT_VOLUME_UP = "volume_up"
ROON_EVENT_VOLUME_DOWN = "volume_down"
