"""Constants for the Tedee integration."""
from datetime import timedelta

DOMAIN = "tedee"
NAME = "Tedee"

SCAN_INTERVAL = timedelta(seconds=10)

CONF_UNLOCK_PULLS_LATCH = "unlock_pulls_latch"
CONF_LOCAL_ACCESS_TOKEN = "local_access_token"
CONF_BRIDGE_ID = "bridge_id"
CONF_HOME_ASSISTANT_ACCESS_TOKEN = "home_assistant_access_token"
CONF_USE_CLOUD = "use_cloud"

ATTR_NUMERIC_STATE = "numeric_state"
ATTR_SUPPORT_PULLSPING = "support_pullspring"
ATTR_DURATION_PULLSPRING = "duration_pullspring"
ATTR_CONNECTED = "connected"
ATTR_SEMI_LOCKED = "semi_locked"
