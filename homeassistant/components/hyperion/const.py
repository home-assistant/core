"""Constants for Hyperion integration."""

CONF_AUTH_ID = "auth_id"
CONF_CREATE_TOKEN = "create_token"
CONF_INSTANCE = "instance"
CONF_ON_UNLOAD = "ON_UNLOAD"
CONF_PRIORITY = "priority"
CONF_ROOT_CLIENT = "ROOT_CLIENT"

DEFAULT_NAME = "Hyperion"
DEFAULT_ORIGIN = "Home Assistant"
DEFAULT_PRIORITY = 128

DOMAIN = "hyperion"

HYPERION_RELEASES_URL = "https://github.com/hyperion-project/hyperion.ng/releases"
HYPERION_VERSION_WARN_CUTOFF = "2.0.0-alpha.9"

SIGNAL_INSTANCES_UPDATED = f"{DOMAIN}_instances_updated_signal." "{}"
SIGNAL_INSTANCE_REMOVED = f"{DOMAIN}_instance_removed_signal." "{}"

TYPE_HYPERION_LIGHT = "hyperion_light"
