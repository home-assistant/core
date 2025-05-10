"""Configuration for Sentry tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.smarla.config_flow import Connection
from homeassistant.components.smarla.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER

from . import MOCK_SERIAL_NUMBER

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_SERIAL_NUMBER,
        source=SOURCE_USER,
    )


@pytest.fixture
def mock_refresh_token_success():
    """Patch Connection.refresh_token to return True."""
    with patch.object(Connection, "refresh_token", new=AsyncMock(return_value=True)):
        yield


@pytest.fixture
def malformed_token_patch():
    """Patch Connection to raise exception."""
    return patch.object(Connection, "__init__", side_effect=ValueError)


@pytest.fixture
def invalid_auth_patch():
    """Patch Connection.refresh_token to return False."""
    return patch.object(Connection, "refresh_token", new=AsyncMock(return_value=False))
