"""Constants for Eurotronic CometBlue tests."""

from uuid import UUID

from homeassistant.const import CONF_PIN

FIXTURE_DEVICE_NAME = "Comet Blue"
FIXTURE_MAC = "aa:bb:cc:dd:ee:ff"
FIXTURE_RSSI = -60
FIXTURE_SERVICE_UUID = "47e9ee00-47e9-11e4-8939-164230d1df67"

FIXTURE_GATT_CHARACTERISTICS = {
    UUID("00002a24-0000-1000-8000-00805f9b34fb"): bytearray(b"Comet Blue"),  # model
    UUID("00002a26-0000-1000-8000-00805f9b34fb"): bytearray(b"0.0.10"),  # version
    UUID("00002a29-0000-1000-8000-00805f9b34fb"): bytearray(
        b"Eurotronic GmbH"
    ),  # manufacturer
    UUID("47e9ee20-47e9-11e4-8939-164230d1df67"): bytearray(
        b'\x80\x1b\x0b\x16\x80\x1b\x0b\x16"'
    ),  # holiday 1
    UUID("47e9ee2b-47e9-11e4-8939-164230d1df67"): bytearray(
        b"/999\x00\x04\n"
    ),  # temperature
    UUID("47e9ee2c-47e9-11e4-8939-164230d1df67"): bytearray(b"48"),  # battery
}

FIXTURE_USER_INPUT = {
    CONF_PIN: "000000",
}
