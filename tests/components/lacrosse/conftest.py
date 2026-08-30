"""Fixtures for LaCrosse integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent config entry setup during config flow tests."""
    with patch(
        "homeassistant.components.lacrosse.async_setup_entry", return_value=True
    ) as mock:
        yield mock
