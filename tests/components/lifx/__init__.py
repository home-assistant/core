"""Tests for the lifx integration."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aiolifx.aiolifx import Light

from homeassistant.components.lifx import discovery
from homeassistant.components.lifx.const import TARGET_ANY

MODULE = "homeassistant.components.lifx"
MODULE_CONFIG_FLOW = "homeassistant.components.lifx.config_flow"
IP_ADDRESS = "127.0.0.1"
LABEL = "My Bulb"
SERIAL = "aa:bb:cc:dd:ee:cc"
MAC_ADDRESS = "aa:bb:cc:dd:ee:cd"
DEFAULT_ENTRY_TITLE = LABEL


class MockMessage:
    """Mock a lifx message."""

    def __init__(self, **kwargs):
        """Init message."""
        self.target_addr = SERIAL
        self.count = 9
        for k, v in kwargs.items():
            if k != "callb":
                setattr(self, k, v)


class MockFailingLifxCommand:
    """Mock a lifx command that fails."""

    def __init__(self, bulb, **kwargs):
        """Init command."""
        self.bulb = bulb
        self.calls = []

    def __call__(self, *args, **kwargs):
        """Call command."""
        if callb := kwargs.get("callb"):
            callb(self.bulb, None)
        self.calls.append([args, kwargs])

    def reset_mock(self):
        """Reset mock."""
        self.calls = []


class MockLifxCommand:
    """Mock a lifx command."""

    def __name__(self):
        """Return name."""
        return "mock_lifx_command"

    def __init__(self, bulb, **kwargs):
        """Init command."""
        self.bulb = bulb
        self.calls = []
        self.msg_kwargs = kwargs

    def __call__(self, *args, **kwargs):
        """Call command."""
        if callb := kwargs.get("callb"):
            callb(self.bulb, MockMessage(**self.msg_kwargs))
        self.calls.append([args, kwargs])

    def reset_mock(self):
        """Reset mock."""
        self.calls = []


def _mocked_bulb() -> Light:
    bulb = Light(asyncio.get_running_loop(), SERIAL, IP_ADDRESS)
    bulb.host_firmware_version = "3.00"
    bulb.label = LABEL
    bulb.color = [1, 2, 3, 4]
    bulb.power_level = 0
    bulb.fire_and_forget = AsyncMock()
    bulb.set_reboot = Mock()
    bulb.try_sending = AsyncMock()
    bulb.set_infrared = MockLifxCommand(bulb)
    bulb.get_color = MockLifxCommand(bulb)
    bulb.set_power = MockLifxCommand(bulb)
    bulb.set_color = MockLifxCommand(bulb)
    bulb.get_hostfirmware = MockLifxCommand(bulb)
    bulb.get_version = MockLifxCommand(bulb)
    bulb.set_waveform_optional = MockLifxCommand(bulb)
    bulb.product = 1  # LIFX Original 1000
    return bulb


def _mocked_failing_bulb() -> Light:
    bulb = _mocked_bulb()
    bulb.get_color = MockFailingLifxCommand(bulb)
    bulb.set_power = MockFailingLifxCommand(bulb)
    bulb.set_color = MockFailingLifxCommand(bulb)
    bulb.get_hostfirmware = MockFailingLifxCommand(bulb)
    bulb.get_version = MockFailingLifxCommand(bulb)
    return bulb


def _mocked_white_bulb() -> Light:
    bulb = _mocked_bulb()
    bulb.product = 19  # LIFX White 900 BR30 (High Voltage)
    return bulb


def _mocked_brightness_bulb() -> Light:
    bulb = _mocked_bulb()
    bulb.product = 51  # LIFX Mini White
    return bulb


def _mocked_clean_bulb() -> Light:
    bulb = _mocked_bulb()
    bulb.get_hev_cycle = MockLifxCommand(
        bulb, duration=7200, remaining=0, last_power=False
    )
    bulb.hev_cycle = {
        "duration": 7200,
        "remaining": 30,
        "last_power": False,
    }
    bulb.product = 90
    return bulb


def _mocked_light_strip() -> Light:
    bulb = _mocked_bulb()
    bulb.product = 31  # LIFX Z
    bulb.get_color_zones = MockLifxCommand(bulb)
    bulb.set_color_zones = MockLifxCommand(bulb)
    bulb.color_zones = [MagicMock(), MagicMock()]
    return bulb


def _mocked_bulb_new_firmware() -> Light:
    bulb = _mocked_bulb()
    bulb.host_firmware_version = "3.90"
    return bulb


def _mocked_relay() -> Light:
    bulb = _mocked_bulb()
    bulb.product = 70  # LIFX Switch
    return bulb


def _patch_device(device: Light | None = None, no_device: bool = False):
    """Patch out discovery."""

    class MockLifxConnecton:
        """Mock lifx discovery."""

        def __init__(self, *args, **kwargs):
            """Init connection."""
            if no_device:
                self.device = _mocked_failing_bulb()
            else:
                self.device = device or _mocked_bulb()
            self.device.mac_addr = TARGET_ANY

        async def async_setup(self):
            """Mock setup."""

        def async_stop(self):
            """Mock teardown."""

    @contextmanager
    def _patcher():
        with patch("homeassistant.components.lifx.LIFXConnection", MockLifxConnecton):
            yield

    return _patcher()


def _patch_discovery(device: Light | None = None, no_device: bool = False):
    """Patch out discovery."""

    class MockLifxDiscovery:
        """Mock lifx discovery."""

        def __init__(self, *args, **kwargs):
            """Init discovery."""
            if no_device:
                self.lights = {}
                return
            discovered = device or _mocked_bulb()
            self.lights = {discovered.mac_addr: discovered}

        def start(self):
            """Mock start."""

        def cleanup(self):
            """Mock cleanup."""

    @contextmanager
    def _patcher():
        with patch.object(discovery, "DEFAULT_TIMEOUT", 0), patch(
            "homeassistant.components.lifx.discovery.LifxDiscovery", MockLifxDiscovery
        ):
            yield

    return _patcher()


def _patch_config_flow_try_connect(
    device: Light | None = None, no_device: bool = False
):
    """Patch out discovery."""

    class MockLifxConnecton:
        """Mock lifx discovery."""

        def __init__(self, *args, **kwargs):
            """Init connection."""
            if no_device:
                self.device = _mocked_failing_bulb()
            else:
                self.device = device or _mocked_bulb()
            self.device.mac_addr = TARGET_ANY

        async def async_setup(self):
            """Mock setup."""

        def async_stop(self):
            """Mock teardown."""

    @contextmanager
    def _patcher():
        with patch(
            "homeassistant.components.lifx.config_flow.LIFXConnection",
            MockLifxConnecton,
        ):
            yield

    return _patcher()
