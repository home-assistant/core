"""Constants for the AVM Fritz!Box call monitor integration."""
from datetime import timedelta

STATE_RINGING = "ringing"
STATE_DIALING = "dialing"
STATE_TALKING = "talking"
STATE_IDLE = "idle"

FRITZ_STATE_RING = "RING"
FRITZ_STATE_CALL = "CALL"
FRITZ_STATE_CONNECT = "CONNECT"
FRITZ_STATE_DISCONNECT = "DISCONNECT"

ICON_PHONE = "mdi:phone"

ATTR_PREFIXES = "prefixes"
ATTR_PHONEBOOK_NAME = "phonebook_name"
ATTR_PHONEBOOK_URL = "phonebook_url"

FRITZ_ATTR_NAME = "name"
FRITZ_ATTR_URL = "url"

UNKOWN_NAME = "unknown"

CONF_PHONEBOOK = "phonebook"
CONF_PREFIXES = "prefixes"

DEFAULT_HOST = "169.254.1.1"  # IP valid for all Fritz!Box routers
DEFAULT_PORT = 1012
DEFAULT_USERNAME = "admin"
DEFAULT_PHONEBOOK = 0

# Return cached results if phonebook was downloaded less then this time ago.
MIN_TIME_PHONEBOOK_UPDATE = timedelta(hours=6)
SCAN_INTERVAL = timedelta(hours=3)
INTERVAL_RECONNECT = 60

DOMAIN = "fritzbox_callmonitor"
MANUFACTURER = "AVM"

PLATFORMS = ["sensor"]
UNDO_UPDATE_LISTENER = "undo_update_listener"
FRITZ_BOX_PHONEBOOK_OBJECT = "fritz_box_phonebook_object"
