"""Common fixtures for the Hue BLE tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    "Override async_setup_entry."
    with patch(
        "homeassistant.components.hue_ble.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None):
    """Auto mock bluetooth."""
