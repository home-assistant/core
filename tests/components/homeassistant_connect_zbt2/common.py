"""Common constants for the Connect ZBT-2 integration tests."""

from homeassistant.helpers.service_info.usb import UsbServiceInfo

USB_DATA_ZBT2 = UsbServiceInfo(
    device="/dev/serial/by-id/usb-Nabu_Casa_ZBT-2_80B54EEFAE18-if01-port0",
    vid="303A",
    pid="4001",
    serial_number="80B54EEFAE18",
    manufacturer="Nabu Casa",
    description="ZBT-2",
)
