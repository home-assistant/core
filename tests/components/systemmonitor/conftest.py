"""Fixtures for the Scrape integration."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Automatically path uuid generator."""
    with patch(
        "homeassistant.components.systemmonitor.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry
