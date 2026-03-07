"""Tests of the EnOcean integration."""

from typing import Final

from homeassistant.components.usb import USBDevice

MODULE = "homeassistant.components.enocean"

MOCK_SERIAL_BY_ID: Final[str] = "/dev/serial/by-id/enocean0"

MOCK_USB_DEVICE: Final[USBDevice] = USBDevice(
    device="/dev/enocean0",
    vid="0403",
    pid="6001",
    serial_number="1234",
    description="USB 300",
    manufacturer="EnOcean GmbH",
)
