"""Test fixtures for file platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant


@pytest.fixture
def is_allowed() -> bool:
    """Parameterize mock_is_allowed_path, default True."""
    return True


@pytest.fixture
def mock_is_allowed_path(
    hass: HomeAssistant, is_allowed: bool
) -> Generator[None, MagicMock]:
    """Mock is_allowed_path method."""
    with patch.object(
        hass.config, "is_allowed_path", return_value=is_allowed
    ) as allowed_path_mock:
        yield allowed_path_mock
