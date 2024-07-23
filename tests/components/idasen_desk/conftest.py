"""IKEA Idasen Desk fixtures."""

from collections.abc import Callable
from unittest import mock
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth):
    """Auto mock bluetooth."""
    with mock.patch(
        "homeassistant.components.idasen_desk.bluetooth.async_ble_device_from_address"
    ):
        yield MagicMock()


@pytest.fixture(autouse=False)
def mock_desk_api():
    """Set up idasen desk API fixture."""
    with mock.patch(
        "homeassistant.components.idasen_desk.coordinator.Desk"
    ) as desk_patched:
        mock_desk = MagicMock()

        def mock_init(
            update_callback: Callable[[int | None], None] | None,
            monitor_height: bool = True,
        ):
            mock_desk.trigger_update_callback = update_callback
            return mock_desk

        desk_patched.side_effect = mock_init

        async def mock_connect(ble_device):
            mock_desk.is_connected = True
            mock_desk.trigger_update_callback(None)

        async def mock_disconnect():
            mock_desk.is_connected = False
            mock_desk.trigger_update_callback(None)

        async def mock_move_to(height: float):
            mock_desk.height_percent = height
            mock_desk.trigger_update_callback(height)

        async def mock_move_up():
            await mock_move_to(100)

        async def mock_move_down():
            await mock_move_to(0)

        mock_desk.connect = AsyncMock(side_effect=mock_connect)
        mock_desk.disconnect = AsyncMock(side_effect=mock_disconnect)
        mock_desk.move_to = AsyncMock(side_effect=mock_move_to)
        mock_desk.move_up = AsyncMock(side_effect=mock_move_up)
        mock_desk.move_down = AsyncMock(side_effect=mock_move_down)
        mock_desk.stop = AsyncMock()
        mock_desk.height = 1
        mock_desk.height_percent = 60
        mock_desk.is_moving = False
        mock_desk.address = "AA:BB:CC:DD:EE:FF"

        yield mock_desk
