"""Tests for the lifx integration."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiolifx.aiolifx import Light
from decorator import contextmanager

from homeassistant.components.lifx import discovery
from homeassistant.components.lifx.const import TARGET_ANY

MODULE = "homeassistant.components.lifx"
MODULE_CONFIG_FLOW = "homeassistant.components.lifx.config_flow"
IP_ADDRESS = "127.0.0.1"
LABEL = "My Bulb"
MAC_ADDRESS = "aa:bb:cc:dd:ee:cc"
PHYSICAL_MAC_ADDRESS_NEW_FIRMWARE = "aa:bb:cc:dd:ee:cd"
DEFAULT_ENTRY_TITLE = LABEL


def _mocked_bulb() -> Light:
    bulb = Light(asyncio.get_running_loop(), MAC_ADDRESS, IP_ADDRESS)
    bulb.host_firmware_version = "3.00"
    bulb.label = LABEL
    bulb.color = [1, 2, 3, 4]
    bulb.power_level = 0
    bulb.set_power = MagicMock()
    bulb.set_color = MagicMock()
    bulb.try_sending = AsyncMock()
    bulb.product = 1  # LIFX Original 1000
    return bulb


def _mocked_white_bulb() -> Light:
    bulb = _mocked_bulb()
    bulb.product = 19  # LIFX White 900 BR30 (High Voltage)
    return bulb


def _mocked_light_strip() -> Light:
    bulb = _mocked_bulb()
    bulb.product = 31  # LIFX Z
    bulb.set_color_zones = MagicMock()
    bulb.color_zones = [MagicMock(), MagicMock()]
    return bulb


def _mocked_bulb_new_firmware() -> Light:
    bulb = _mocked_bulb()
    bulb.host_firmware_version = "3.90"
    return bulb


class MockMessage:
    """Mock a lifx message."""

    def __init__(self):
        """Init message."""
        self.target_addr = MAC_ADDRESS
        self.count = 9


class MockExecuteAwaitAioLIFX:
    """Mock and execute an AwaitAioLIFX."""

    async def wait(self, call, *args, **kwargs):
        """Wait."""
        call()
        return MockMessage()


class MockAwaitAioLIFXNoConnection:
    """Mock AwaitAioLIFX."""

    async def wait(*args, **kwargs):
        """Wait."""
        return None


def _patch_device(
    device: Light | None = None, no_device: bool = False, await_mock: Any = None
):
    """Patch out discovery."""

    class MockLifxConnecton:
        """Mock lifx discovery."""

        def __init__(self, *args, **kwargs):
            """Init connection."""
            self.device = device or _mocked_bulb()
            self.device.mac_addr = TARGET_ANY

        async def async_setup(self):
            """Mock setup."""

        def async_stop(self):
            """Mock teardown."""

    if not await_mock:
        await_mock = (
            MockAwaitAioLIFXNoConnection if no_device else MockExecuteAwaitAioLIFX
        )

    @contextmanager
    def _patcher():
        with patch(
            "homeassistant.components.lifx.coordinator.AwaitAioLIFX", await_mock
        ), patch("homeassistant.components.lifx.LIFXConnection", MockLifxConnecton):
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
            self.device = device or _mocked_bulb()
            self.device.mac_addr = TARGET_ANY

        async def async_setup(self):
            """Mock setup."""

        def async_stop(self):
            """Mock teardown."""

    await_mock = MockAwaitAioLIFXNoConnection if no_device else MockExecuteAwaitAioLIFX

    @contextmanager
    def _patcher():
        with patch(
            "homeassistant.components.lifx.config_flow.AwaitAioLIFX", await_mock
        ), patch(
            "homeassistant.components.lifx.config_flow.LIFXConnection",
            MockLifxConnecton,
        ):
            yield

    return _patcher()
