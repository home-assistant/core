"""Constants for the KDEConnect integration."""
from typing import Final

from pykdeconnect.const import KdeConnectDeviceType

DOMAIN: Final = "kdeconnect"

DATA_KEY_CLIENT: Final = "instance"
DATA_KEY_STORAGE: Final = "storage"
DATA_KEY_NAMES: Final = "device_names"
DATA_KEY_DEVICES: Final = "devices"

DEVICE_NAME: Final = "Home Assistant"
DEVICE_TYPE: Final = KdeConnectDeviceType.UNKNOWN

CONF_DEVICE_NAME: Final = "device_name"
CONF_DEVICE_TYPE: Final = "device_type"
CONF_DEVICE_CERT: Final = "device_cert"
CONF_DEVICE_INCOMING_CAPS: Final = "device_incoming_capabilities"
CONF_DEVICE_OUTGOING_CAPS: Final = "device_outgoing_capabilities"

CONF_REFRESH: Final = "Refresh"

CONNECT_TIMEOUT: Final = 2
