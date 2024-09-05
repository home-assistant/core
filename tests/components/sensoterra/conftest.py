"""Common fixtures for the Sensoterra tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from .const import API_TOKEN


@pytest.fixture
def mock_get_token() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with (
        patch(
            "sensoterra.customerapi.CustomerApi.get_token",
            return_value=API_TOKEN,
        ) as mock_entry,
    ):
        yield mock_entry
