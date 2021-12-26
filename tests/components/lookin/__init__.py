"""Tests for the lookin integration."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from aiolookin import Climate, Device, Remote

from homeassistant.components.zeroconf import ZeroconfServiceInfo

DEVICE_ID = "98F33163"
MODULE = "homeassistant.components.lookin"
MODULE_CONFIG_FLOW = "homeassistant.components.lookin.config_flow"
IP_ADDRESS = "127.0.0.1"

DEVICE_NAME = "Living Room"
DEFAULT_ENTRY_TITLE = DEVICE_NAME

ZC_NAME = f"LOOKin_{DEVICE_ID}"
ZC_TYPE = "_lookin._tcp."
ZEROCONF_DATA = ZeroconfServiceInfo(
    host=IP_ADDRESS,
    hostname=f"{ZC_NAME.lower()}.local.",
    port=80,
    type=ZC_TYPE,
    name=ZC_NAME,
    properties={},
)


def _mocked_climate() -> Climate:
    climate = MagicMock(auto_spec=Climate)
    return climate


def _mocked_remote() -> Remote:
    remote = MagicMock(auto_spec=Remote)
    return remote


def _mocked_device() -> Device:
    device = MagicMock(auto_spec=Device)
    device.name = DEVICE_NAME
    device.id = DEVICE_ID
    return device


def _patch_get_info(device=None, exception=None):
    async def _get_info(*args, **kwargs):
        if exception:
            raise exception
        return device if device else _mocked_device()

    return patch(f"{MODULE_CONFIG_FLOW}.LookInHttpProtocol.get_info", new=_get_info)
