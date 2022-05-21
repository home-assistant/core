"""Constants for the AVM Fritz!Box call monitor integration."""
from typing import Final

from homeassistant.backports.enum import StrEnum
from homeassistant.const import Platform


class FritzState(StrEnum):
    """Fritz!Box call states."""

    RING = "RING"
    CALL = "CALL"
    CONNECT = "CONNECT"
    DISCONNECT = "DISCONNECT"


ICON_PHONE: Final = "mdi:phone"

ATTR_PREFIXES = "prefixes"

FRITZ_ACTION_GET_INFO = "GetInfo"
FRITZ_ATTR_NAME = "name"
FRITZ_ATTR_SERIAL_NUMBER = "NewSerialNumber"
FRITZ_SERVICE_DEVICE_INFO = "DeviceInfo"

UNKNOWN_NAME = "unknown"
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

DOMAIN: Final = "fritzbox_callmonitor"
MANUFACTURER: Final = "AVM"

PLATFORMS = [Platform.SENSOR]
UNDO_UPDATE_LISTENER: Final = "undo_update_listener"
FRITZBOX_PHONEBOOK: Final = "fritzbox_phonebook"
