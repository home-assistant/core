"""Constants for Hyperion integration."""

CONF_AUTH_ID = "auth_id"
CONF_CREATE_TOKEN = "create_token"
CONF_INSTANCE = "instance"
CONF_INSTANCE_CLIENTS = "INSTANCE_CLIENTS"
CONF_ON_UNLOAD = "ON_UNLOAD"
CONF_PRIORITY = "priority"
CONF_ROOT_CLIENT = "ROOT_CLIENT"
CONF_EFFECT_HIDE_LIST = "effect_hide_list"
CONF_EFFECT_SHOW_LIST = "effect_show_list"

DEFAULT_NAME = "Hyperion"
DEFAULT_ORIGIN = "Home Assistant"
DEFAULT_PRIORITY = 128

DOMAIN = "hyperion"

HYPERION_MANUFACTURER_NAME = "Hyperion"
HYPERION_MODEL_NAME = f"{HYPERION_MANUFACTURER_NAME}-NG"
HYPERION_RELEASES_URL = "https://github.com/hyperion-project/hyperion.ng/releases"
HYPERION_VERSION_WARN_CUTOFF = "2.0.0-alpha.9"

NAME_SUFFIX_HYPERION_LIGHT = ""
NAME_SUFFIX_HYPERION_PRIORITY_LIGHT = "Priority"
NAME_SUFFIX_HYPERION_COMPONENT_SWITCH = "Component"

SIGNAL_INSTANCE_ADD = f"{DOMAIN}_instance_add_signal." "{}"
SIGNAL_INSTANCE_REMOVE = f"{DOMAIN}_instance_remove_signal." "{}"
SIGNAL_ENTITY_REMOVE = f"{DOMAIN}_entity_remove_signal." "{}"

TYPE_HYPERION_LIGHT = "hyperion_light"
TYPE_HYPERION_PRIORITY_LIGHT = "hyperion_priority_light"
TYPE_HYPERION_COMPONENT_SWITCH_BASE = "hyperion_component_switch"
