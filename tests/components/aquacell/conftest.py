"""Common fixtures for the Aquacell tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.aquacell.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_aquacell_api() -> Generator[AsyncMock, None, None]:
    """Build a fixture for the Aquacell API that authenticates successfully."""
    with (
        patch(
            "homeassistant.components.aquacell.AquacellApi",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.aquacell.config_flow.AquacellApi",
            new=mock_client,
        ),
    ):
        mock_aquacell_api = mock_client.return_value
        mock_aquacell_api.authenticate.return_value = "refresh-token"
        yield mock_aquacell_api
