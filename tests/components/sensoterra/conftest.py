"""Common fixtures for the Sensoterra tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from .const import API_TOKEN


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sensoterra.async_setup_entry",
        return_value=True,
    ) as mock_entry:
        yield mock_entry


@pytest.fixture
def mock_customer_api_client() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with (
        patch(
            "homeassistant.components.sensoterra.config_flow.CustomerApi",
            autospec=True,
        ) as mock_client,
    ):
        mock = mock_client.return_value
        mock.get_token.return_value = API_TOKEN
        yield mock
