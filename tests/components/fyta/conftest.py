"""Test helpers."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_fyta():
    """Build a fixture for the Fyta API that connects successfully and returns one device."""

    mock_fyta_api = AsyncMock()
    with patch(
        "homeassistant.components.fyta.config_flow.FytaConnector",
        return_value=mock_fyta_api,
    ) as mock_fyta_api:
        mock_fyta_api.return_value.login.return_value = {}
        yield mock_fyta_api


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.fyta.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
