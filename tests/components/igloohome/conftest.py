"""Common fixtures for the igloohome tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.igloohome.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def auth_successful():
    """Set up the Auth module to always successfully operate."""
    return patch(
        "igloohome_api.Auth.async_get_access_token",
        return_value="mock_access_token",
    )
