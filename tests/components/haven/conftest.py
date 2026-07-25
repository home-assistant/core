"""Fixtures for HAVEN IAQ tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent config flow tests from setting up the integration."""
    with patch(
        "homeassistant.components.haven.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup
