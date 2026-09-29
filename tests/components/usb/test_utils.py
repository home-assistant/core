"""Tests for the USB integration's device identity helpers."""

import pytest

from homeassistant.components.usb import serial_path_udev_id


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        # CDC ACM links have no port suffix
        (
            "/dev/serial/by-id/usb-Nabu_Casa_ZBT-2_10B41DE589E4-if00",
            "usb-Nabu_Casa_ZBT-2_10B41DE589E4-if00",
        ),
        # `usb-serial` drivers add one, which the proxy cannot know about
        (
            "/dev/serial/by-id/usb-Nabu_Casa_Home_Assistant_Connect_ZBT-1_a28a310e2bedec118f3d4540ad51a8b2-if00-port0",
            "usb-Nabu_Casa_Home_Assistant_Connect_ZBT-1_a28a310e2bedec118f3d4540ad51a8b2-if00",
        ),
        (
            "/dev/serial/by-id/usb-FTDI_Quad_RS232-HS-if00-port3",
            "usb-FTDI_Quad_RS232-HS-if00",
        ),
        (
            "esphome-hass://esphome/01M0EP649N48N88Z52ZG2B21VT"
            "?port_name=USB+%28Zigbee%29"
            "&port_udev_id=usb-Nabu_Casa_ZBT-2_10B41DE589E4-if00",
            "usb-Nabu_Casa_ZBT-2_10B41DE589E4-if00",
        ),
        # These name a socket, not a device
        ("/dev/ttyUSB0", None),
        ("/dev/serial/by-path/pci-0000:00:14.0-usb-0:1:1.0-port0", None),
        ("esphome-hass://esphome/01M0EP649N48N88Z52ZG2B21VT?port_name=UART", None),
        ("socket://192.168.1.10:6638", None),
    ],
)
def test_serial_path_udev_id(path: str, expected: str | None) -> None:
    """A path identifies its device by udev link name only where it has one."""
    assert serial_path_udev_id(path) == expected
