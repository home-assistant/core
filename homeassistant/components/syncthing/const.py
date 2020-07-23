"""Constants for the syncthing integration."""
from datetime import timedelta

DOMAIN = "syncthing"
DEFAULT_NAME = "syncthing"
DEFAULT_PORT = 8384

CONF_USE_HTTPS = "use_https"
DEFAULT_USE_HTTPS = False

RECONNECT_INTERVAL = timedelta(seconds=10)
