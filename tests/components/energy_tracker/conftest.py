"""Common fixtures for Energy Tracker tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir





@pytest.fixture
def mock_hass() -> HomeAssistant:
    """Return a mock HomeAssistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    hass.config = MagicMock()
    hass.config.language = "en"
    return hass


@pytest.fixture
def mock_issue_registry(mock_hass: HomeAssistant) -> Generator[MagicMock]:
    """Mock the issue registry."""
    with patch.object(ir, "async_create_issue") as mock_create:
        yield mock_create


@pytest.fixture
def api_token() -> str:
    """Return a test API token."""
    return "test-token-12345678"


@pytest.fixture
def device_id() -> str:
    """Return a valid UUID device ID."""
    return "12345678-1234-1234-1234-123456789abc"
