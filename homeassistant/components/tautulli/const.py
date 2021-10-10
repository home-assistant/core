"""Constants for the Tautulli integration."""
from logging import Logger, getLogger

CONF_MONITORED_USERS = "monitored_users"
DATA_KEY_API = "api"
DATA_KEY_COORDINATOR = "coordinator"
DEFAULT_NAME = "Tautulli"
DEFAULT_PATH = ""
DEFAULT_PORT = "8181"
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True
DOMAIN = "tautulli"

LOGGER: Logger = getLogger(__package__)
