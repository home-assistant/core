"""Constants for the AVM Fritz!Box call monitor integration."""

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

FRITZ_ACTION_GET_INFO = "GetInfo"
FRITZ_ATTR_NAME = "name"
FRITZ_ATTR_SERIAL_NUMBER = "NewSerialNumber"
FRITZ_SERVICE_DEVICE_INFO = "DeviceInfo"

UNKOWN_NAME = "unknown"
SERIAL_NUMBER = "serial_number"
REGEX_NUMBER = r"[^\d\+]"

CONF_PHONEBOOK = "phonebook"
CONF_PHONEBOOK_NAME = "phonebook_name"
CONF_PREFIXES = "prefixes"

DEFAULT_HOST = "169.254.1.1"  # IP valid for all Fritz!Box routers
DEFAULT_PORT = 1012
DEFAULT_USERNAME = "admin"
DEFAULT_PHONEBOOK = 0
DEFAULT_NAME = "Phone"

DOMAIN = "fritzbox_callmonitor"
MANUFACTURER = "AVM"

PLATFORMS = ["sensor"]
UNDO_UPDATE_LISTENER = "undo_update_listener"
FRITZBOX_PHONEBOOK = "fritzbox_phonebook"
