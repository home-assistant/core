"""Fixtures for the Sesame BLE integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture(autouse=True)
def mock_config_flow_sesame_device() -> Generator[MagicMock]:
    """Mock SesameDevice in config flow for connection and authentication."""
    with patch(
        "homeassistant.components.sesame_ble.config_flow.SesameDevice"
    ) as mock_dev_class:
        mock_device = MagicMock()
        mock_device.connect = AsyncMock()
        mock_device.login = AsyncMock()
        mock_device.disconnect = AsyncMock()
        mock_device.register = AsyncMock(
            return_value="0123456789abcdef0123456789abcdef"
        )
        mock_dev_class.return_value = mock_device
        yield mock_device
