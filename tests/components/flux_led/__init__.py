"""Tests for the flux_led integration."""
from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch

from flux_led import WifiLedBulb
from flux_led.const import (
    COLOR_MODE_CCT as FLUX_COLOR_MODE_CCT,
    COLOR_MODE_RGB as FLUX_COLOR_MODE_RGB,
)
from flux_led.protocol import LEDENETRawState

from homeassistant.components.dhcp import (
    HOSTNAME as DHCP_HOSTNAME,
    IP_ADDRESS as DHCP_IP_ADDRESS,
    MAC_ADDRESS as DHCP_MAC_ADDRESS,
)
from homeassistant.components.flux_led.const import FLUX_HOST, FLUX_MAC, FLUX_MODEL

MODULE = "homeassistant.components.flux_led"
MODULE_CONFIG_FLOW = "homeassistant.components.flux_led.config_flow"
IP_ADDRESS = "127.0.0.1"
MODEL = "AZ120444"
MAC_ADDRESS = "aa:bb:cc:dd:ee:ff"
FLUX_MAC_ADDRESS = "aabbccddeeff"

DEFAULT_ENTRY_TITLE = f"{MODEL} {FLUX_MAC_ADDRESS}"

DHCP_DISCOVERY = {
    DHCP_HOSTNAME: MODEL,
    DHCP_IP_ADDRESS: IP_ADDRESS,
    DHCP_MAC_ADDRESS: MAC_ADDRESS,
}
FLUX_DISCOVERY = {FLUX_HOST: IP_ADDRESS, FLUX_MODEL: MODEL, FLUX_MAC: FLUX_MAC_ADDRESS}


def _mocked_bulb() -> WifiLedBulb:
    bulb = MagicMock(auto_spec=WifiLedBulb)
    bulb.getRgb = MagicMock(return_value=[255, 0, 0])
    bulb.getRgbw = MagicMock(return_value=[255, 0, 0, 50])
    bulb.getRgbww = MagicMock(return_value=[255, 0, 0, 50, 0])
    bulb.getRgbcw = MagicMock(return_value=[255, 0, 0, 0, 50])
    bulb.rgb = (255, 0, 0)
    bulb.rgbw = (255, 0, 0, 50)
    bulb.rgbww = (255, 0, 0, 50, 0)
    bulb.rgbcw = (255, 0, 0, 0, 50)
    bulb.getWhiteTemperature = MagicMock(return_value=(2700, 128))
    bulb.brightness = 128
    bulb.model_num = 0x35
    bulb.rgbwcapable = True
    bulb.color_modes = {FLUX_COLOR_MODE_RGB, FLUX_COLOR_MODE_CCT}
    bulb.color_mode = FLUX_COLOR_MODE_RGB
    bulb.raw_state = LEDENETRawState(
        0, 0x35, 0, 0x61, 0x5, 50, 255, 0, 0, 50, 8, 0, 0, 0
    )
    return bulb


def _patch_discovery(device=None, no_device=False):
    def _discovery(*args, **kwargs):
        if no_device:
            return []
        return [FLUX_DISCOVERY]

    return patch("homeassistant.components.flux_led.BulbScanner.scan", new=_discovery)


def _patch_wifibulb(device=None, no_device=False):
    def _wifi_led_bulb(*args, **kwargs):
        if no_device:
            raise socket.timeout
        return device if device else _mocked_bulb()

    return patch("homeassistant.components.flux_led.WifiLedBulb", new=_wifi_led_bulb)
