"""Common constants for the SkyConnect integration tests."""

from homeassistant.helpers.service_info.usb import UsbServiceInfo

USB_DATA_SKY = UsbServiceInfo(
    device="/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0_9e2adbd75b8beb119fe564a0f320645d-if00-port0",
    vid="10C4",
    pid="EA60",
    serial_number="9e2adbd75b8beb119fe564a0f320645d",
    manufacturer="Nabu Casa",
    description="SkyConnect v1.0",
)

USB_DATA_ZBT1 = UsbServiceInfo(
    device="/dev/serial/by-id/usb-Nabu_Casa_Home_Assistant_Connect_ZBT-1_9e2adbd75b8beb119fe564a0f320645d-if00-port0",
    vid="10C4",
    pid="EA60",
    serial_number="9e2adbd75b8beb119fe564a0f320645d",
    manufacturer="Nabu Casa",
    description="Home Assistant Connect ZBT-1",
)
