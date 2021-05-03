"""Common fixtures and objects for the Switcher integration tests."""
from __future__ import annotations

from asyncio import Queue
from datetime import datetime
from typing import Any, Generator
from unittest.mock import AsyncMock, patch

from pytest import fixture

from .consts import (
    DUMMY_AUTO_OFF_SET,
    DUMMY_DEVICE_ID,
    DUMMY_DEVICE_NAME,
    DUMMY_DEVICE_PASSWORD,
    DUMMY_DEVICE_STATE,
    DUMMY_ELECTRIC_CURRENT,
    DUMMY_IP_ADDRESS,
    DUMMY_MAC_ADDRESS,
    DUMMY_PHONE_ID,
    DUMMY_POWER_CONSUMPTION,
    DUMMY_REMAINING_TIME,
)


@patch("aioswitcher.devices.SwitcherV2Device")
class MockSwitcherV2Device:
    """Class for mocking the aioswitcher.devices.SwitcherV2Device object."""

    def __init__(self) -> None:
        """Initialize the object."""
        self._last_state_change = datetime.now()

    @property
    def device_id(self) -> str:
        """Return the device id."""
        return DUMMY_DEVICE_ID

    @property
    def ip_addr(self) -> str:
        """Return the ip address."""
        return DUMMY_IP_ADDRESS

    @property
    def mac_addr(self) -> str:
        """Return the mac address."""
        return DUMMY_MAC_ADDRESS

    @property
    def name(self) -> str:
        """Return the device name."""
        return DUMMY_DEVICE_NAME

    @property
    def state(self) -> str:
        """Return the device state."""
        return DUMMY_DEVICE_STATE

    @property
    def remaining_time(self) -> str | None:
        """Return the time left to auto-off."""
        return DUMMY_REMAINING_TIME

    @property
    def auto_off_set(self) -> str:
        """Return the auto-off configuration value."""
        return DUMMY_AUTO_OFF_SET

    @property
    def power_consumption(self) -> int:
        """Return the power consumption in watts."""
        return DUMMY_POWER_CONSUMPTION

    @property
    def electric_current(self) -> float:
        """Return the power consumption in amps."""
        return DUMMY_ELECTRIC_CURRENT

    @property
    def phone_id(self) -> str:
        """Return the phone id."""
        return DUMMY_PHONE_ID

    @property
    def device_password(self) -> str:
        """Return the device password."""
        return DUMMY_DEVICE_PASSWORD

    @property
    def last_data_update(self) -> datetime:
        """Return the timestamp of the last update."""
        return datetime.now()

    @property
    def last_state_change(self) -> datetime:
        """Return the timestamp of the state change."""
        return self._last_state_change


@fixture(name="mock_bridge")
def mock_bridge_fixture() -> Generator[None, Any, None]:
    """Fixture for mocking aioswitcher.bridge.SwitcherV2Bridge."""
    queue = Queue()

    async def mock_queue():
        """Mock asyncio's Queue."""
        await queue.put(MockSwitcherV2Device())
        return await queue.get()

    mock_bridge = AsyncMock()

    patchers = [
        patch(
            "homeassistant.components.switcher_kis.SwitcherV2Bridge.start",
            new=mock_bridge,
        ),
        patch(
            "homeassistant.components.switcher_kis.SwitcherV2Bridge.stop",
            new=mock_bridge,
        ),
        patch(
            "homeassistant.components.switcher_kis.SwitcherV2Bridge.queue",
            get=mock_queue,
        ),
        patch(
            "homeassistant.components.switcher_kis.SwitcherV2Bridge.running",
            return_value=True,
        ),
    ]

    for patcher in patchers:
        patcher.start()

    yield

    for patcher in patchers:
        patcher.stop()


@fixture(name="mock_failed_bridge")
def mock_failed_bridge_fixture() -> Generator[None, Any, None]:
    """Fixture for mocking aioswitcher.bridge.SwitcherV2Bridge."""

    async def mock_queue():
        """Mock asyncio's Queue."""
        raise RuntimeError

    patchers = [
        patch(
            "homeassistant.components.switcher_kis.SwitcherV2Bridge.start",
            return_value=None,
        ),
        patch(
            "homeassistant.components.switcher_kis.SwitcherV2Bridge.stop",
            return_value=None,
        ),
        patch(
            "homeassistant.components.switcher_kis.SwitcherV2Bridge.queue",
            get=mock_queue,
        ),
    ]

    for patcher in patchers:
        patcher.start()

    yield

    for patcher in patchers:
        patcher.stop()


@fixture(name="mock_api")
def mock_api_fixture() -> Generator[AsyncMock, Any, None]:
    """Fixture for mocking aioswitcher.api.SwitcherV2Api."""
    mock_api = AsyncMock()

    patchers = [
        patch(
            "homeassistant.components.switcher_kis.switch.SwitcherV2Api.connect",
            new=mock_api,
        ),
        patch(
            "homeassistant.components.switcher_kis.switch.SwitcherV2Api.disconnect",
            new=mock_api,
        ),
    ]

    for patcher in patchers:
        patcher.start()

    yield

    for patcher in patchers:
        patcher.stop()
