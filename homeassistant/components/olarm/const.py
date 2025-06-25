"""Constants for the olarm integration."""

DOMAIN = "olarm"
OAUTH2_AUTHORIZE = "https://oauth.olarm.com/oauth2/authorize"
OAUTH2_TOKEN = "https://oauth.olarm.com/oauth2/token"
OAUTH2_CLIENT_ID = "4at9g5tkr5mpbv9bi2m9qa2dal"
OAUTH2_CLIENT_SECRET = ""  # Public OAuth client

# Service constants
SERVICE_ZONE_BYPASS = "zone_bypass"
SERVICE_ZONE_UNBYPASS = "zone_unbypass"
SERVICE_PGM_COMMAND = "pgm_command"
SERVICE_UTILITY_KEY = "utility_key"
SERVICE_LINK_OUTPUT_COMMAND = "link_output_command"
SERVICE_LINK_RELAY_COMMAND = "link_relay_command"
SERVICE_MAX_OUTPUT_COMMAND = "max_output_command"

# Service attributes
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_ZONE_INDEX = "zone_index"
ATTR_PGM_INDEX = "pgm_index"
ATTR_PGM_ACTION = "pgm_action"
ATTR_UKEY_INDEX = "ukey_index"
ATTR_LINK_ID = "link_id"
ATTR_OUTPUT_INDEX = "output_index"
ATTR_OUTPUT_ACTION = "output_action"
ATTR_RELAY_INDEX = "relay_index"
ATTR_RELAY_ACTION = "relay_action"
