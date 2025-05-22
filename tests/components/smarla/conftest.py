"""Configuration for smarla tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pysmarlaapi.classes import AuthToken
from pysmarlaapi.federwiege.classes import Property
import pytest

from homeassistant.components.smarla.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER

from .const import MOCK_ACCESS_TOKEN_JSON, MOCK_SERIAL_NUMBER, MOCK_USER_INPUT

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
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.smarla.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_connection() -> Generator[MagicMock]:
    """Patch Connection object."""
    with (
        patch(
            "homeassistant.components.smarla.config_flow.Connection", autospec=True
        ) as mock_connection,
        patch(
            "homeassistant.components.smarla.Connection",
            mock_connection,
        ),
    ):
        connection = mock_connection.return_value
        connection.token = AuthToken.from_json(MOCK_ACCESS_TOKEN_JSON)
        connection.refresh_token.return_value = True
        yield connection


@pytest.fixture
def mock_federwiege(
    mock_connection: AsyncMock, mock_property: AsyncMock
) -> Generator[AsyncMock]:
    """Mock the Federwiege instance."""
    with patch(
        "homeassistant.components.smarla.Federwiege", autospec=True
    ) as mock_federwiege:
        federwiege = mock_federwiege.return_value
        federwiege.serial_number = MOCK_SERIAL_NUMBER
        federwiege.get_property.return_value = mock_property
        yield federwiege


@pytest.fixture
def mock_property() -> AsyncMock:
    """Mock the Federwiege instance."""
    mock = AsyncMock(spec=Property)
    mock.get.return_value = False
    return mock
