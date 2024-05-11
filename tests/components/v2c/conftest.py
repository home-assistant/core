"""Common fixtures for the V2C tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.v2c.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_v2c_client() -> Generator[AsyncMock, None, None]:
    """Mock a V2C client."""
    with (
        patch(
            "homeassistant.components.v2c.Trydan",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.v2c.config_flow.Trydan",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_data.return_value = {}
        yield client
