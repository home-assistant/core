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
    """Mock api."""
    with (
        patch("librouteros.create_transport"),
        patch("librouteros.Api.readResponse") as mock_api,
    ):
        yield mock_api
