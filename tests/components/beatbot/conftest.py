"""Test fixtures for the Beatbot integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent config-flow tests from setting up the integration."""
    with patch(
        "homeassistant.components.beatbot.async_setup_entry", return_value=True
    ) as setup_entry:
        yield setup_entry
