"""Mikrotik test configuration."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from . import create_mock_config_entry


@pytest.fixture
def mock_config_entry():
    """Create Mikrotik config entries with optional overrides."""
    return create_mock_config_entry


@pytest.fixture(autouse=True)
def mock_api() -> Generator[MagicMock]:
    """Mock the librouteros API instance returned by librouteros.connect."""
    api_instance = MagicMock()

    with patch("librouteros.connect", return_value=api_instance):
        yield api_instance
