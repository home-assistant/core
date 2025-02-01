"""Tests for the USB Discovery integration."""

from homeassistant.components.usb.models import USBDevice

conbee_device = USBDevice(
    device="/dev/cu.usbmodemDE24338801",
    vid="1CF1",
    pid="0030",
    serial_number="DE2433880",
    manufacturer="dresden elektronik ingenieurtechnik GmbH",
    description="ConBee II",
)
slae_sh_device = USBDevice(
    device="/dev/cu.usbserial-110",
    vid="10C4",
    pid="EA60",
    serial_number="00_12_4B_00_22_98_88_7F",
    manufacturer="Silicon Labs",
    description="slae.sh cc2652rb stick - slaesh's iot stuff",
)
electro_lama_device = USBDevice(
    device="/dev/cu.usbserial-110",
    vid="1A86",
    pid="7523",
    serial_number=None,
    manufacturer=None,
    description="USB2.0-Serial",
)
skyconnect_macos_correct = USBDevice(
    device="/dev/cu.SLAB_USBtoUART",
    vid="10C4",
    pid="EA60",
    serial_number="9ab1da1ea4b3ed11956f4eaca7669f5d",
    manufacturer="Nabu Casa",
    description="SkyConnect v1.0",
)
skyconnect_macos_incorrect = USBDevice(
    device="/dev/cu.usbserial-2110",
    vid="10C4",
    pid="EA60",
    serial_number="9ab1da1ea4b3ed11956f4eaca7669f5d",
    manufacturer="Nabu Casa",
    description="SkyConnect v1.0",
)
