"""Tests for the lifx integration."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from aiolifx.aiolifx import Light
from decorator import contextmanager

from homeassistant.components.lifx import discovery

MODULE = "homeassistant.components.lifx"
MODULE_CONFIG_FLOW = "homeassistant.components.lifx.config_flow"
IP_ADDRESS = "127.0.0.1"
LABEL = "My Bulb"
MAC_ADDRESS = "aa:bb:cc:dd:ee:ff"
DEFAULT_ENTRY_TITLE = LABEL


def _mocked_bulb() -> Light:
    bulb = Light(asyncio.get_running_loop(), MAC_ADDRESS, IP_ADDRESS)
    bulb.host_firmware_version = "3.00"
    bulb.label = LABEL
    return bulb


class MockAwaitAioLIFX:
    """Mock AwaitAioLIFX."""

    async def wait(*args, **kwargs):
        """Wait."""
        return MagicMock(target_addr=MAC_ADDRESS)


class MockAwaitAioLIFXNoConnection:
    """Mock AwaitAioLIFX."""

    async def wait(*args, **kwargs):
        """Wait."""
        return None


def _patch_device(device: Light | None = None, no_device: bool = False):
    """Patch out discovery."""

    class MockLifxConnecton:
        """Mock lifx discovery."""

        def __init__(self, *args, **kwargs):
            """Init connection."""
            self.device = device or _mocked_bulb()

        async def async_setup(self):
            """Mock setup."""

        def async_stop(self):
            """Mock teardown."""

    await_mock = MockAwaitAioLIFXNoConnection if no_device else MockAwaitAioLIFX

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

        async def async_setup(self):
            """Mock setup."""

        def async_stop(self):
            """Mock teardown."""

    await_mock = MockAwaitAioLIFXNoConnection if no_device else MockAwaitAioLIFX

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
