"""Fixtures for Mikrotik methods."""
from unittest.mock import patch

import pytest


@pytest.fixture(name="api")
def mock_api():
    """Mock an api."""
    with patch("librouteros.connect") as mock_api:
        yield mock_api
