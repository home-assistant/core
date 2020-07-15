"""Constants for the Control4 integration."""

DOMAIN = "control4"

DEFAULT_SCAN_INTERVAL = 10
MIN_SCAN_INTERVAL = 1

CONF_LIGHT_TRANSITION_TIME = "light_transition_time"
CONF_LIGHT_COLD_START_TRANSITION_TIME = "light_cold_start_transition_time"
DEFAULT_LIGHT_TRANSITION_TIME = 0
DEFAULT_LIGHT_COLD_START_TRANSITION_TIME = 3

CONF_ACCOUNT = "account"
CONF_DIRECTOR = "director"
CONF_DIRECTOR_TOKEN_EXPIRATION = "director_token_expiry"
CONF_DIRECTOR_SW_VERSION = "director_sw_version"
CONF_DIRECTOR_MODEL = "director_model"
CONF_DIRECTOR_ALL_ITEMS = "director_all_items"
CONF_CONTROLLER_UNIQUE_ID = "controller_unique_id"

CONF_CONFIG_LISTENER = "config_listener"

CONTROL4_ENTITY_TYPE = 7
