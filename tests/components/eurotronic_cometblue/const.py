"""Constants for Eurotronic CometBlue tests."""

from uuid import UUID

from homeassistant.components.eurotronic_cometblue.const import CONF_RETRY_COUNT
from homeassistant.const import CONF_PIN, CONF_TIMEOUT

FIXTURE_DEVICE_NAME = "Comet Blue"
FIXTURE_MAC = "aa:bb:cc:dd:ee:ff"
FIXTURE_RSSI = -60
FIXTURE_SERVICE_UUID = "47e9ee00-47e9-11e4-8939-164230d1df67"

FIXTURE_GATT_CHARACTERISTICS = {
    UUID("00002a28-0000-1000-8000-00805f9b34fb"): bytearray(b"0.0.10"),
    UUID("00002a29-0000-1000-8000-00805f9b34fb"): bytearray(b"Eurotronic GmbH"),
}

FIXTURE_USER_INPUT = {
    CONF_PIN: 0,
    CONF_TIMEOUT: 20,
    CONF_RETRY_COUNT: 3,
}
