"""Constants for the KDEConnect integration."""

from pykdeconnect.const import KdeConnectDeviceType

DOMAIN = "kdeconnect"

DATA_KEY_CLIENT = "instance"
DATA_KEY_STORAGE = "storage"
DATA_KEY_NAMES = "device_names"
DATA_KEY_DEVICES = "devices"

DEVICE_NAME = "Home Assistant"
DEVICE_TYPE = KdeConnectDeviceType.UNKNOWN

CONF_DEVICE_NAME = "device_name"
CONF_DEVICE_TYPE = "device_type"
CONF_DEVICE_CERT = "device_cert"
CONF_DEVICE_INCOMING_CAPS = "device_incoming_capabilities"
CONF_DEVICE_OUTGOING_CAPS = "device_outgoing_capabilities"

CONF_REFRESH = "Refresh"

CONNECT_TIMEOUT = 2
