"""Test configuration for Mitsubishi-Climaveneta iMXW fancoil."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Make sure we never actually run setup."""
    with patch(
        "homeassistant.components.climaveneta_imxw.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
