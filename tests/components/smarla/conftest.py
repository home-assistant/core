"""Configuration for Sentry tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from pysmarlaapi.classes import AuthToken
import pytest

from homeassistant.components.smarla.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER

from . import MOCK_ACCESS_TOKEN_JSON, MOCK_SERIAL_NUMBER, MOCK_USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_SERIAL_NUMBER,
        source=SOURCE_USER,
        data=MOCK_USER_INPUT,
    )


@pytest.fixture
def mock_connection():
    """Patch Connection object."""
    with (
        patch(
            "homeassistant.components.smarla.config_flow.Connection"
        ) as mock_connection,
        patch(
            "homeassistant.components.smarla.Connection",
            mock_connection,
        ),
    ):
        connection = MagicMock()
        connection.token = AuthToken.from_json(MOCK_ACCESS_TOKEN_JSON)
        connection.refresh_token = AsyncMock(return_value=True)
        mock_connection.return_value = connection
        yield connection
