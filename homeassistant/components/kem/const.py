"""Constants for the KEM integration."""

from datetime import timedelta
from typing import Final

from aiokem import CommunicationError

DOMAIN = "kem"

CE_RT_COORDINATORS = "coordinators"
CE_RT_KEM = "kem"
CE_RT_HOMES = "homes"


DD_DEVICES = "devices"
DD_PRODUCT = "product"
DD_FIRMWARE_VERSION = "firmwareVersion"
DD_MODEL_NAME = "modelDisplayName"
DD_ID = "id"
DD_DISPLAY_NAME = "displayName"
DD_MAC_ADDRESS = "macAddress"
DD_IS_CONNECTED = "isConnected"

KOHLER = "Kohler"

GD_DEVICE = "device"

CONNECTION_EXCEPTIONS = (
    TimeoutError,
    CommunicationError,
)

RPM: Final = "rpm"

SCAN_INTERVAL_MINUTES = timedelta(minutes=10)
