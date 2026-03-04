"""Configuration for smarla tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pysmarlaapi import AuthToken
from pysmarlaapi.federwiege.services.classes import Property, Service
from pysmarlaapi.federwiege.services.types import UpdateStatus
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

        def mocked_connection(url, token_b64: str):
            connection.token = AuthToken.from_base64(token_b64)
            return connection

        mock_connection.side_effect = mocked_connection

        yield connection


def _mock_babywiege_service() -> MagicMock:
    mock_babywiege_service = MagicMock(spec=Service)
    mock_babywiege_service.props = {
        "swing_active": MagicMock(spec=Property),
        "smart_mode": MagicMock(spec=Property),
        "intensity": MagicMock(spec=Property),
    }

    mock_babywiege_service.props["swing_active"].get.return_value = False
    mock_babywiege_service.props["smart_mode"].get.return_value = False
    mock_babywiege_service.props["intensity"].get.return_value = 1

    return mock_babywiege_service


def _mock_analyser_service() -> MagicMock:
    mock_analyser_service = MagicMock(spec=Service)
    mock_analyser_service.props = {
        "oscillation": MagicMock(spec=Property),
        "activity": MagicMock(spec=Property),
        "swing_count": MagicMock(spec=Property),
    }

    mock_analyser_service.props["oscillation"].get.return_value = [0, 0]
    mock_analyser_service.props["activity"].get.return_value = 0
    mock_analyser_service.props["swing_count"].get.return_value = 0

    return mock_analyser_service


def _mock_info_service() -> MagicMock:
    mock_info_service = MagicMock(spec=Service)
    mock_info_service.props = {
        "version": MagicMock(spec=Property),
    }

    mock_info_service.props["version"].get.return_value = "1.0.0"

    return mock_info_service


def _mock_system_service() -> MagicMock:
    mock_system_service = MagicMock(spec=Service)
    mock_system_service.props = {
        "firmware_update": MagicMock(spec=Property),
        "firmware_update_status": MagicMock(spec=Property),
    }

    mock_system_service.props["firmware_update"].get.return_value = 0
    mock_system_service.props[
        "firmware_update_status"
    ].get.return_value = UpdateStatus.IDLE

    return mock_system_service


@pytest.fixture
def mock_federwiege_cls(mock_connection: MagicMock) -> Generator[MagicMock]:
    """Mock the Federwiege class."""
    with patch(
        "homeassistant.components.smarla.Federwiege", autospec=True
    ) as mock_federwiege_cls:
        mock_federwiege = mock_federwiege_cls.return_value
        mock_federwiege.serial_number = MOCK_ACCESS_TOKEN_JSON["serialNumber"]
        mock_federwiege.available = True

        mock_federwiege.check_firmware_update = AsyncMock(return_value=("1.0.0", ""))

        mock_federwiege.services = {
            "babywiege": _mock_babywiege_service(),
            "analyser": _mock_analyser_service(),
            "info": _mock_info_service(),
            "system": _mock_system_service(),
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
