"""Constants for the Rehlko integration."""

from aiokem import CommunicationError

DOMAIN = "rehlko"

CONF_REFRESH_TOKEN = "refresh_token"

DEVICE_DATA_DEVICES = "devices"
DEVICE_DATA_PRODUCT = "product"
DEVICE_DATA_FIRMWARE_VERSION = "firmwareVersion"
DEVICE_DATA_MODEL_NAME = "modelDisplayName"
DEVICE_DATA_ID = "id"
DEVICE_DATA_DISPLAY_NAME = "displayName"
DEVICE_DATA_MAC_ADDRESS = "macAddress"
DEVICE_DATA_IS_CONNECTED = "isConnected"

KOHLER = "Kohler"

GENERATOR_DATA_DEVICE = "device"

CONNECTION_EXCEPTIONS = (
    TimeoutError,
    CommunicationError,
)
