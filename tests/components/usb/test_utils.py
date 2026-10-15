"""Tests for the USB integration's device identity helpers."""

import pytest

from homeassistant.components.usb import serial_path_udev_id


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        pytest.param(
            "/dev/serial/by-id/usb-Nabu_Casa_ZBT-2_10B41DE589E4-if00",
            "usb-Nabu_Casa_ZBT-2_10B41DE589E4-if00",
            id="by_id_cdc_acm",
        ),
        pytest.param(
            "/dev/serial/by-id/usb-Nabu_Casa_Home_Assistant_Connect_ZBT-1_a28a310e2bedec118f3d4540ad51a8b2-if00-port0",
            "usb-Nabu_Casa_Home_Assistant_Connect_ZBT-1_a28a310e2bedec118f3d4540ad51a8b2-if00-port0",
            id="by_id_usb_serial",
        ),
        pytest.param(
            "esphome-hass://esphome/01M0EP649N48N88Z52ZG2B21VT"
            "?port_udev_id=usb-Nabu_Casa_ZBT-2_10B41DE589E4-if00",
            "usb-Nabu_Casa_ZBT-2_10B41DE589E4-if00",
            id="serial_proxy",
        ),
        pytest.param("/dev/ttyUSB0", None, id="raw_path"),
        pytest.param("/dev/ttyAMA1", None, id="uart"),
        pytest.param(
            "/dev/serial/by-path/pci-0000:00:14.0-usb-0:1:1.0-port0",
            None,
            id="by_path",
        ),
        pytest.param(
            "esphome-hass://esphome/01M0EP649N48N88Z52ZG2B21VT?port_name=UART",
            None,
            id="serial_proxy_by_name",
        ),
        pytest.param("socket://192.168.1.10:6638", None, id="socket"),
    ],
)
def test_serial_path_udev_id(path: str, expected: str | None) -> None:
    """A path identifies its device by udev link name only where it has one."""
    assert serial_path_udev_id(path) == expected
