"""Configuration for smarla tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pysmarlaapi.federwiege.services.classes import Property, Service
import pytest

from homeassistant.components.smarla.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER

from .const import MOCK_ACCESS_TOKEN_JSON, MOCK_USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_ACCESS_TOKEN_JSON["serialNumber"],
        source=SOURCE_USER,
        data=MOCK_USER_INPUT,
    )


@pytest.fixture
def mock_setup_entry() -> Generator:
    """Override async_setup_entry."""
    with patch("homeassistant.components.smarla.async_setup_entry", return_value=True):
        yield


@pytest.fixture
def mock_refresh_token() -> Generator[AsyncMock]:
    """Mock the refresh token function."""
    with patch(
        "homeassistant.components.smarla.Connection.refresh_token",
        autospec=True,
    ) as mock_refresh:
        yield mock_refresh


@pytest.fixture
def mock_federwiege_cls(mock_refresh_token: MagicMock) -> Generator[MagicMock]:
    """Mock the Federwiege class."""
    with patch(
        "homeassistant.components.smarla.Federwiege", autospec=True
    ) as mock_federwiege_cls:
        mock_federwiege = mock_federwiege_cls.return_value
        mock_federwiege.serial_number = MOCK_ACCESS_TOKEN_JSON["serialNumber"]

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

        mock_federwiege.services = {
            "babywiege": mock_babywiege_service,
            "analyser": mock_analyser_service,
        }

        mock_federwiege.get_property = MagicMock(
            side_effect=lambda service, prop: mock_federwiege.services[service].props[
                prop
            ]
        )

        yield mock_federwiege_cls


@pytest.fixture
def mock_federwiege(mock_federwiege_cls: MagicMock) -> Generator[MagicMock]:
    """Mock the Federwiege instance."""
    return mock_federwiege_cls.return_value
