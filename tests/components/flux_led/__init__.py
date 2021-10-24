"""Tests for the flux_led integration."""
from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch

from flux_led import WifiLedBulb

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
    bulb.brightness = 128
    bulb.rgbwcapable = True
    bulb.raw_state = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
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
