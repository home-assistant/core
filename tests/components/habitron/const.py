"""Constants used by the Habitron test suite."""

from typing import Final

MOCK_HOST: Final = "192.168.1.50"
MOCK_HOST_HOSTNAME: Final = "smarthub.local"
MOCK_PORT: Final = 7777
MOCK_MAC: Final = "AA:BB:CC:DD:EE:FF"
MOCK_UID: Final = "AABBCCDDEEFF"
MOCK_NAME: Final = "Habitron SmartHub"
MOCK_VERSION: Final = "5.1.0"
MOCK_HWTYPE: Final = "Raspberry Pi 4 Model B"
MOCK_SERIAL: Final = "HBT-123456"
MOCK_UDN: Final = "uuid:12345678-1234-1234-1234-123456789abc"
MOCK_WEBSOCK_TOKEN: Final = "test-token-not-real"

MOCK_CONFIG_DATA: Final = {
    "habitron_host": MOCK_HOST,
    "websock_token": MOCK_WEBSOCK_TOKEN,
}

MOCK_CONFIG_OPTIONS: Final = {
    "habitron_host": MOCK_HOST,
    "websock_token": MOCK_WEBSOCK_TOKEN,
}

# Module type bytes used internally by Habitron.
TYPE_SMART_CONTROLLER: Final = b"\x01\x03"
TYPE_SMART_CONTROLLER_TOUCH: Final = b"\x01\x04"
TYPE_SMART_OUT8R: Final = b"\x32\x01"
