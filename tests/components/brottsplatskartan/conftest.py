"""Test fixtures for Brottplatskartan."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.brottsplatskartan.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def uuid_generator() -> Generator[AsyncMock]:
    """Generate uuid for app-id."""
    with patch(
        "homeassistant.components.brottsplatskartan.config_flow.uuid.getnode",
        return_value="1234567890",
    ) as uuid_generator:
        yield uuid_generator
