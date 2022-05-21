"""Constants for the Tautulli integration."""
from logging import Logger, getLogger
from typing import Final

ATTR_TOP_USER = "top_user"

CONF_MONITORED_USERS = "monitored_users"
DEFAULT_NAME = "Tautulli"
DEFAULT_PATH = ""
DEFAULT_PORT = "8181"
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True
DOMAIN: Final = "tautulli"
LOGGER: Logger = getLogger(__package__)
