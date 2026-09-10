"""Tests for the USB integration's device identity helpers."""

import pytest

from homeassistant.components.usb import (
    async_resolve_serial_port,
    udev_serial_by_id_names,
    usb_device_matches_serial_path,
)
from homeassistant.components.usb.models import USBDevice
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import patch_scanned_serial_ports

BY_ID = "/dev/serial/by-id"
PROXY_URL = (
    "esphome-hass://esphome/01M0EP649N48N88Z52ZG2B21VT"
    "?port_name=USB+%28Zigbee%29&usb_serial=10B41DE589E4"
)

# A ZBT-2 as an ESPHome device reports it: the same fields Linux reports for the same stick
ZBT2_PROXIED = USBDevice(
    device=PROXY_URL,
    resolved_device=PROXY_URL,
    vid="303A",
    pid="4001",
    serial_number="10B41DE589E4",
    manufacturer="Nabu Casa",
    description="ZBT-2 - Nabu Casa ZBT-2",
    bcd_device=0x0101,
    interface_description="Nabu Casa ZBT-2",
    interface_num=0,
)
ZBT2_LOCAL_PATH = f"{BY_ID}/usb-Nabu_Casa_ZBT-2_10B41DE589E4-if00"


def _device(**fields: object) -> USBDevice:
    base: dict[str, object] = {
        "device": "/dev/ttyUSB0",
        "vid": "0000",
        "pid": "0000",
        "serial_number": None,
        "manufacturer": None,
        "description": None,
        "interface_num": 0,
    }
    base.update(fields)
    return USBDevice(**base)  # type: ignore[arg-type]


# Expected names are taken from udev on real hosts (serialx's sysfs dumps)
@pytest.mark.parametrize(
    ("device", "expected"),
    [
        pytest.param(
            ZBT2_PROXIED,
            [ZBT2_LOCAL_PATH, f"{ZBT2_LOCAL_PATH}-port0"],
            id="cdc_acm_with_interface_string",
        ),
        pytest.param(
            _device(
                vid="303A",
                pid="4001",
                manufacturer="Nabu Casa",
                description="Home Assistant Connect ZBT-1",
                serial_number="a28a310e2bedec118f3d4540ad51a8b2",
            ),
            [
                f"{BY_ID}/usb-Nabu_Casa_Home_Assistant_Connect_ZBT-1"
                "_a28a310e2bedec118f3d4540ad51a8b2-if00",
                f"{BY_ID}/usb-Nabu_Casa_Home_Assistant_Connect_ZBT-1"
                "_a28a310e2bedec118f3d4540ad51a8b2-if00-port0",
            ],
            id="cp210x_spaces_and_dashes",
        ),
        pytest.param(
            _device(
                vid="0403",
                pid="6001",
                manufacturer="FTDI",
                description="FT232R USB UART",
                serial_number="A5069RR4",
            ),
            [
                f"{BY_ID}/usb-FTDI_FT232R_USB_UART_A5069RR4-if00",
                f"{BY_ID}/usb-FTDI_FT232R_USB_UART_A5069RR4-if00-port0",
            ],
            id="ftdi",
        ),
        pytest.param(
            _device(
                vid="067B",
                pid="2303",
                manufacturer="Prolific Technology Inc.",
                description="USB-Serial Controller",
                serial_number="DSDCb147613",
            ),
            [
                f"{BY_ID}/usb-Prolific_Technology_Inc._USB-Serial_Controller"
                "_DSDCb147613-if00",
                f"{BY_ID}/usb-Prolific_Technology_Inc._USB-Serial_Controller"
                "_DSDCb147613-if00-port0",
            ],
            id="dot_is_kept",
        ),
        pytest.param(
            _device(
                vid="10C4",
                pid="EA60",
                manufacturer="Silicon Labs",
                description="CP2102 USB to UART Bridge Controller",
                serial_number="41b06ea8",
            ),
            [
                f"{BY_ID}/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller"
                "_41b06ea8-if00",
                f"{BY_ID}/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller"
                "_41b06ea8-if00-port0",
            ],
            id="long_product",
        ),
        pytest.param(
            _device(vid="1A86", pid="7523", description="USB Serial"),
            [
                f"{BY_ID}/usb-1a86_USB_Serial-if00",
                f"{BY_ID}/usb-1a86_USB_Serial-if00-port0",
            ],
            id="no_manufacturer_no_serial_uses_hex_vendor",
        ),
        pytest.param(
            _device(vid="1A86", pid="55D4", serial_number="0001", interface_num=1),
            [
                f"{BY_ID}/usb-1a86_55d4_0001-if01",
                f"{BY_ID}/usb-1a86_55d4_0001-if01-port0",
            ],
            id="no_strings_second_interface",
        ),
        pytest.param(
            _device(
                vid="0000",
                pid="0000",
                manufacturer="  Odd  Vendor/Name\t",
                description="Ünïcode ok, (parens) not",
                serial_number="S N",
            ),
            [
                f"{BY_ID}/usb-Odd_Vendor_Name_Ünïcode_ok___parens__not_S_N-if00",
                f"{BY_ID}/usb-Odd_Vendor_Name_Ünïcode_ok___parens__not_S_N-if00-port0",
            ],
            id="sanitizer_rules",
        ),
    ],
)
def test_udev_serial_by_id_names(device: USBDevice, expected: list[str]) -> None:
    """The synthesized names match what udev produces on a Linux host."""
    assert udev_serial_by_id_names(device) == expected


@pytest.mark.parametrize(
    ("device", "path", "matches"),
    [
        pytest.param(ZBT2_PROXIED, PROXY_URL, True, id="same_path"),
        pytest.param(ZBT2_PROXIED, ZBT2_LOCAL_PATH, True, id="by_id_of_proxied"),
        pytest.param(
            ZBT2_PROXIED,
            f"{BY_ID}/usb-Nabu_Casa_ZBT-2_FFFFFFFFFFFF-if00",
            False,
            id="by_id_other_serial",
        ),
        pytest.param(
            _device(
                device=ZBT2_LOCAL_PATH,
                vid="303A",
                pid="4001",
                serial_number="10B41DE589E4",
                manufacturer="Nabu Casa",
                description="ZBT-2 - Nabu Casa ZBT-2",
                interface_description="Nabu Casa ZBT-2",
            ),
            PROXY_URL,
            True,
            id="url_of_local",
        ),
        pytest.param(
            _device(device=ZBT2_LOCAL_PATH, vid="303A", pid="4001", serial_number="X"),
            PROXY_URL,
            False,
            id="url_other_serial",
        ),
        pytest.param(
            _device(
                device=ZBT2_LOCAL_PATH,
                vid="1A86",
                pid="7523",
                serial_number="10B41DE589E4",
            ),
            f"{PROXY_URL}&vid=303A&pid=4001",
            False,
            id="url_vid_pid_disagree",
        ),
        pytest.param(
            _device(
                device=ZBT2_LOCAL_PATH,
                vid="303A",
                pid="4001",
                serial_number="10B41DE589E4",
            ),
            f"{PROXY_URL}&vid=303a&pid=4001",
            True,
            id="url_vid_pid_agree_any_case",
        ),
        pytest.param(
            _device(device=ZBT2_LOCAL_PATH, serial_number="10B41DE589E4"),
            "esphome-hass://esphome/entry?port_name=RS-232+Port+1",
            False,
            id="url_without_pin_is_a_socket",
        ),
        pytest.param(
            _device(device="/dev/ttyUSB0", serial_number="10B41DE589E4"),
            "/dev/ttyUSB1",
            False,
            id="device_node_is_a_socket",
        ),
        pytest.param(
            _device(device=ZBT2_LOCAL_PATH, serial_number=None),
            "esphome-hass://esphome/entry?port_name=USB&usb_serial=",
            False,
            id="empty_serial_pins_nothing",
        ),
    ],
)
def test_usb_device_matches_serial_path(
    device: USBDevice, path: str, matches: bool
) -> None:
    """A stored path is recognized by the identity it carries, not where it points."""
    assert usb_device_matches_serial_path(device, path) is matches


@pytest.mark.usefixtures("force_usb_polling_watcher")
async def test_async_resolve_serial_port(hass: HomeAssistant) -> None:
    """A stored path resolves to the one present port that is the same adapter."""
    assert await async_setup_component(hass, "usb", {})

    # The stick moved from the host to an ESPHome device
    with patch_scanned_serial_ports(return_value=[ZBT2_PROXIED]):
        assert await async_resolve_serial_port(hass, ZBT2_LOCAL_PATH) == PROXY_URL
        # Present where it is stored: nothing to resolve
        assert await async_resolve_serial_port(hass, PROXY_URL) == PROXY_URL
        # Another adapter entirely
        assert (
            await async_resolve_serial_port(
                hass, f"{BY_ID}/usb-Nabu_Casa_ZBT-2_FFFFFFFFFFFF-if00"
            )
            is None
        )

    # And back to the host
    local = USBDevice(
        device=ZBT2_LOCAL_PATH,
        vid="303A",
        pid="4001",
        serial_number="10B41DE589E4",
        manufacturer="Nabu Casa",
        description="ZBT-2 - Nabu Casa ZBT-2",
        interface_description="Nabu Casa ZBT-2",
        interface_num=0,
    )
    with patch_scanned_serial_ports(return_value=[local]):
        assert await async_resolve_serial_port(hass, PROXY_URL) == ZBT2_LOCAL_PATH

    # Two identical adapters without serial numbers cannot be told apart
    twins = [
        _device(
            device="/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0",
            vid="1A86",
            pid="7523",
            description="USB Serial",
        ),
        _device(
            device="esphome-hass://esphome/entry?port_name=USB",
            vid="1A86",
            pid="7523",
            description="USB Serial",
        ),
    ]
    with patch_scanned_serial_ports(return_value=twins):
        assert (
            await async_resolve_serial_port(
                hass, f"{BY_ID}/usb-1a86_USB_Serial-if01-port0"
            )
            is None
        )

    # Nothing present at all
    with patch_scanned_serial_ports(return_value=[]):
        assert await async_resolve_serial_port(hass, ZBT2_LOCAL_PATH) is None
