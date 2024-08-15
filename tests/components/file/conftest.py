"""Test fixtures for file platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.file.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def is_allowed() -> bool:
    """Parameterize mock_is_allowed_path, default True."""
    return True


@pytest.fixture
def mock_is_allowed_path(hass: HomeAssistant, is_allowed: bool) -> Generator[MagicMock]:
    """Mock is_allowed_path method."""
    with patch.object(
        hass.config, "is_allowed_path", return_value=is_allowed
    ) as allowed_path_mock:
        yield allowed_path_mock
