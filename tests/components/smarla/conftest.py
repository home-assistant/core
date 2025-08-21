"""Configuration for smarla tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from pysmarlaapi.classes import AuthToken
from pysmarlaapi.federwiege.classes import Property, Service
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
def mock_setup_entry() -> Generator:
    """Override async_setup_entry."""
    with patch("homeassistant.components.smarla.async_setup_entry", return_value=True):
        yield


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
def mock_federwiege(mock_connection: MagicMock) -> Generator[MagicMock]:
    """Mock the Federwiege instance."""
    with patch(
        "homeassistant.components.smarla.Federwiege", autospec=True
    ) as mock_federwiege:
        federwiege = mock_federwiege.return_value
        federwiege.serial_number = MOCK_SERIAL_NUMBER

        mock_babywiege_service = MagicMock(spec=Service)
        mock_babywiege_service.props = {
            "swing_active": MagicMock(spec=Property),
            "smart_mode": MagicMock(spec=Property),
            "intensity": MagicMock(spec=Property),
        }

        mock_babywiege_service.props["swing_active"].get.return_value = False
        mock_babywiege_service.props["smart_mode"].get.return_value = False
        mock_babywiege_service.props["intensity"].get.return_value = 1

        mock_analyser_service = MagicMock(spec=Service)
        mock_analyser_service.props = {
            "oscillation": MagicMock(spec=Property),
            "activity": MagicMock(spec=Property),
            "swing_count": MagicMock(spec=Property),
        }

        mock_analyser_service.props["oscillation"].get.return_value = [0, 0]
        mock_analyser_service.props["activity"].get.return_value = 0
        mock_analyser_service.props["swing_count"].get.return_value = 0

        federwiege.services = {
            "babywiege": mock_babywiege_service,
            "analyser": mock_analyser_service,
        }

        federwiege.get_property = MagicMock(
            side_effect=lambda service, prop: federwiege.services[service].props[prop]
        )

        yield federwiege
