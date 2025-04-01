"""Satel Integra tests configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override integration setup."""
    with patch(
        "homeassistant.components.satel_integra.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_satel() -> Generator[AsyncMock]:
    """Override the satel test."""
    with (
        patch(
            "homeassistant.components.satel_integra.AsyncSatel",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.satel_integra.config_flow.AsyncSatel",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value

        yield client
