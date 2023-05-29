"""Common fixtures for the Schlage tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.schlage.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_schlage():
    """Mock pyschlage.Schlage."""
    with patch("pyschlage.Schlage", autospec=True) as mock_schlage:
        yield mock_schlage.return_value


@pytest.fixture
def mock_pyschlage_auth():
    """Mock pyschlage.Auth."""
    with patch("pyschlage.Auth", autospec=True) as mock_auth:
        yield mock_auth.return_value
