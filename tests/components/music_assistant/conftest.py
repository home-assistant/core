"""Music Assistant test fixtures."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from tests.components.smhi.common import AsyncMock


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.music_assistant.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry
