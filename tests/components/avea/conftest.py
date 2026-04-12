"""Avea fixtures."""

from collections.abc import Generator
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_bluetooth(mock_bluetooth_history: None, enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture(autouse=True)
def mock_bluetooth_history() -> Generator[None]:
    """Avoid accessing host bluetooth history during tests."""
    with patch(
        "homeassistant.components.bluetooth.manager.async_load_history_from_system",
        return_value=({}, {}),
    ):
        yield
