"""Shared test configuration and fixtures for the RYSE integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_ryse_ble_device() -> Generator[MagicMock]:
    """Auto-patch RyseBLEDevice so tests never touch real BLE hardware.

    Applied automatically to every test in this package. Individual tests that
    need to inspect the mock can request this fixture by name.
    """
    device = MagicMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    device.update_callback = None
    device.client = None

    # Sensible defaults for position helpers
    device.is_valid_position.return_value = True
    device.get_real_position.side_effect = lambda x: 100 - x
    device.is_closed.side_effect = lambda x: x == 100

    # BLE commands are coroutines
    device.pair = AsyncMock(return_value=True)
    device.send_open = AsyncMock()
    device.send_close = AsyncMock()
    device.send_set_position = AsyncMock()
    device.send_get_position = AsyncMock()

    with patch(
        "homeassistant.components.ryse.cover.RyseBLEDevice",
        return_value=device,
    ) as mock_cls:
        mock_cls.return_value = device
        yield device
