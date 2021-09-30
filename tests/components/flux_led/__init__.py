"""Tests for the flux_led integration."""
from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch

from flux_led import WifiLedBulb

from homeassistant.components.flux_led.const import FLUX_HOST, FLUX_MAC, FLUX_MODEL

MODULE = "homeassistant.flux_led.tplink"
MODULE_CONFIG_FLOW = "homeassistant.components.flux_led.config_flow"
IP_ADDRESS = "127.0.0.1"
ALIAS = "My Bulb"
MODEL = "AZ120444"
MAC_ADDRESS = "aabbccddeeff"
DEFAULT_ENTRY_TITLE = f"{ALIAS} {MODEL}"


def _mocked_discovered_bulb() -> dict[str, str]:
    return {FLUX_HOST: IP_ADDRESS, FLUX_MODEL: MODEL, FLUX_MAC: MAC_ADDRESS}


def _mocked_bulb() -> WifiLedBulb:
    bulb = MagicMock(auto_spec=WifiLedBulb)
    return bulb


def _patch_discovery(device=None, no_device=False):
    async def _discovery(*args, **kwargs):
        if no_device:
            return []
        return [_mocked_discovered_bulb()]

    return patch("homeassistant.components.flux_led.BulbScanner.scan", new=_discovery)


def _patch_wifibulb(device=None, no_device=False):
    async def _mocked_bulb(*_):
        if no_device:
            raise socket.timeout
        return device if device else _mocked_bulb()

    return patch("homeassistant.components.flux_led.WifiLedBulb", new=_mocked_bulb)
