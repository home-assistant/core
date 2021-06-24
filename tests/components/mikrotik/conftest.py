"""Conftest for mikrotik."""
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_api():
    """Mock api."""
    with patch("librouteros.connect") as mock_api:
        yield mock_api
