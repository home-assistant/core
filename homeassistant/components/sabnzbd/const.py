"""Constants for the Sabnzbd component."""
from datetime import timedelta

DOMAIN = "sabnzbd"
DATA_SABNZBD = "sabnzbd"

_CONFIGURING = {}

ATTR_SPEED = "speed"
BASE_URL_FORMAT = "{}://{}:{}/"
CONFIG_FILE = "sabnzbd.conf"
DEFAULT_HOST = "localhost"
DEFAULT_NAME = "SABnzbd"
DEFAULT_PORT = 8080
DEFAULT_SPEED_LIMIT = "100"
DEFAULT_SSL = False

UPDATE_INTERVAL = timedelta(seconds=30)

SERVICE_PAUSE = "pause"
SERVICE_RESUME = "resume"
SERVICE_SET_SPEED = "set_speed"

SIGNAL_SABNZBD_UPDATED = "sabnzbd_updated"

KEY_API = "api"
KEY_NAME = "name"
