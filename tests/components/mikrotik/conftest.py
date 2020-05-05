"""Fixtures for Mikrotik methods."""
import pytest

from tests.async_mock import patch


@pytest.fixture(name="api")
def mock_api():
    """Mock an api."""
    with patch("librouteros.connect") as mock_api:
        yield mock_api
