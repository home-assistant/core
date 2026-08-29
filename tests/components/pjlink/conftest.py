"""Common fixtures for the PJLink tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.pjlink.const import DOMAIN

from .const import DEFAULT_DATA

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.pjlink.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""

    return MockConfigEntry(
        version=1, domain=DOMAIN, title="test name", data=DEFAULT_DATA
    )


@pytest.fixture
def mock_projector() -> Generator[MagicMock]:
    """Mock the PJLink Projector in the config flow."""
    with patch(
        "homeassistant.components.pjlink.config_flow.Projector",
        autospec=True,
    ) as mock_projector:
        mock_instance = mock_projector.from_address.return_value
        mock_instance.get_name.return_value = "test name"
        mock_instance.__enter__.return_value = mock_instance
        yield mock_projector
