"""Test fixtures for Wake on Lan."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_send_magic_packet() -> AsyncMock:
    """Mock magic packet."""
    with patch("wakeonlan.send_magic_packet") as mock_send:
        yield mock_send
