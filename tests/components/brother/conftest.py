"""Test fixtures for brother."""
from collections.abc import Generator
import sys
from unittest.mock import AsyncMock, patch

import pytest

if sys.version_info >= (3, 12):
    collect_ignore_glob = ["test_*.py"]


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.brother.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
