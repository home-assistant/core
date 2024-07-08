"""Common fixtures for the Sensoterra tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from .const import API_TOKEN


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with (
        patch(
            "homeassistant.components.sensoterra.async_setup_entry",
            return_value=True,
        ),
        patch(
            "sensoterra.customerapi.CustomerApi.get_token",
            return_value=API_TOKEN,
        ) as mock_setup_entry,
    ):
        yield mock_setup_entry
