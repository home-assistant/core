"""Tests of the EnOcean integration."""

from homeassistant.components.usb import USBDevice, usb_service_info_from_device
from homeassistant.helpers.service_info.usb import UsbServiceInfo

MODULE = "homeassistant.components.enocean"

MOCK_SERIAL_BY_ID: str = "/dev/serial/by-id/enocean0"

MOCK_USB_DEVICE: USBDevice = USBDevice(
    device="/dev/enocean0",
    vid="0403",
    pid="6001",
    serial_number="1234",
    description="USB 300",
    manufacturer="EnOcean GmbH",
)

MOCK_USB_SERVICE_INFO: UsbServiceInfo = usb_service_info_from_device(MOCK_USB_DEVICE)
