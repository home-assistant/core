"""Test fixtures for Wake on Lan."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_send_magic_packet() -> AsyncMock:
    """Mock magic packet."""
    with patch("wakeonlan.send_magic_packet") as mock_send:
        yield mock_send


@pytest.fixture
def subprocess_call_return_value() -> int | None:
    """Return value for subprocess."""
    return 1


@pytest.fixture(autouse=True)
def mock_subprocess_call(
    subprocess_call_return_value: int,
) -> Generator[None, None, MagicMock]:
    """Mock magic packet."""
    with patch("homeassistant.components.wake_on_lan.switch.sp.call") as mock_sp:
        mock_sp.return_value = subprocess_call_return_value
        yield mock_sp
