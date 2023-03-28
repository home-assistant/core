"""Provide common mystrom fixtures and mocks."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.mystrom.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


class ResponseMock:
    """Mock class for aiohttp response."""

    def __init__(self, json: dict, status: int):
        """Initialize the response mock."""
        self._json = json
        self.status = status

    @property
    def headers(self) -> dict:
        """Headers of the response."""
        return {"Content-Type": "application/json"}

    async def json(self) -> dict:
        """Return the json content of the response."""
        return self._json

    async def __aexit__(self, exc_type, exc, tb):
        """Exit."""
        pass

    async def __aenter__(self):
        """Enter."""
        return self
