"""Tests for the TP-Link component."""

from unittest.mock import AsyncMock, MagicMock, patch

from kasa import SmartBulb
from kasa.exceptions import SmartDeviceException

MODULE = "homeassistant.components.tplink"
MODULE_CONFIG_FLOW = "homeassistant.components.tplink.config_flow"
IP_ADDRESS = "127.0.0.1"
ALIAS = "My Bulb"
MODEL = "HS100"
MAC_ADDRESS = "aa:bb:cc:dd:ee:ff"
DEFAULT_ENTRY_TITLE = f"{ALIAS} {MODEL}"


def _mocked_bulb() -> SmartBulb:
    bulb = MagicMock(auto_spec=SmartBulb)
    bulb.update = AsyncMock()
    bulb.mac = MAC_ADDRESS
    bulb.alias = ALIAS
    bulb.model = MODEL
    bulb.host = IP_ADDRESS
    bulb.brightness = 255
    bulb.color_temp = 4000
    bulb.device_id = MAC_ADDRESS
    bulb.valid_temperature_range.min = 9000
    bulb.valid_temperature_range.max = 4000
    bulb.hw_info = {"sw_ver": "1.0.0"}
    return bulb


def _patch_discovery(no_device=False):
    async def _discovery(*_):
        if no_device:
            return {}
        return {IP_ADDRESS: _mocked_bulb()}

    return patch("homeassistant.components.tplink.Discover.discover", new=_discovery)


def _patch_single_discovery(no_device=False):
    async def _discover_single(*_):
        if no_device:
            raise SmartDeviceException
        return _mocked_bulb()

    return patch(
        "homeassistant.components.tplink.Discover.discover_single", new=_discover_single
    )
