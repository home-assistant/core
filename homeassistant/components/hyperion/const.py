"""Constants for Hyperion integration."""
DOMAIN = "hyperion"

DEFAULT_NAME = "Hyperion"
DEFAULT_ORIGIN = "Home Assistant"
DEFAULT_PRIORITY = 128

CONF_AUTH_ID = "auth_id"
CONF_CREATE_TOKEN = "create_token"
CONF_INSTANCE = "instance"
CONF_PRIORITY = "priority"

CONF_ROOT_CLIENT = "ROOT_CLIENT"
CONF_ON_UNLOAD = "ON_UNLOAD"

SIGNAL_INSTANCES_UPDATED = f"{DOMAIN}_instances_updated_signal." "{}"
SIGNAL_INSTANCE_REMOVED = f"{DOMAIN}_instance_removed_signal." "{}"

SOURCE_IMPORT = "import"
