"""Fixtures for ViCare integration tests."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from . import MODULE


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(f"{MODULE}.async_setup_entry", return_value=True) as mock_setup_entry:
        yield mock_setup_entry
