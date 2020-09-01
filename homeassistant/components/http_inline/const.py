"""Const for the http_inline integration."""


DOMAIN = "http_inline"
PLATFORMS = ["switch"]

CONF_PATH_PATTERN_READ = "path_read"
CONF_PATH_PATTERN_WRITE = "path_write"
CONF_RELAYS = "relays"
CONF_NB_RELAYS = "nb_relays"
CONF_RELAY_NAMES = "relay_names"
CONF_RELAY_I_NAME_PATTERN = "relay_name_{}"

DEFAULT_HOST = "http://webrelay.local"
DEFAULT_NAME = "http_inline switch"
DEFAULT_PATH_PATTERN_READ = "/r/{relay_id}"
DEFAULT_PATH_PATTERN_WRITE = "/w/{relay_id}/{state}"
DEFAULT_NB_RELAYS = "0"
