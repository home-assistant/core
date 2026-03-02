"""Tests of the EnOcean integration."""

from homeassistant.components.usb import USBDevice

MODULE = "homeassistant.components.enocean"

MOCK_USB_DEVICE: USBDevice = USBDevice(
    device="/dev/ttyUSB1234",
    vid="0403",
    pid="6001",
    serial_number="12345678",
    manufacturer="EnOcean",
    description="usb 300",
)
