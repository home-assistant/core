"""Common fixtures for the Nintendo Switch Parental Controls tests."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from pynintendoparental.device import Device
import pytest

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain="nintendo_parental",
        data={"session_token": "valid_token"},
        unique_id="aabbccddee112233",
    )


@pytest.fixture
def mock_nintendo_device() -> Device:
    """Return a mocked device."""
    mock = AsyncMock(spec=Device)
    mock.device_id = "testdevid"
    mock.name = "Home Assistant Test"
    mock.extra = {"device": {"firmwareVersion": {"displayedVersion": "99.99.99"}}}
    mock.limit_time = 120
    mock.today_playing_time = 110
    return mock


@pytest.fixture
def mock_nintendo_authenticator() -> Generator[MagicMock]:
    """Mock Nintendo Authenticator."""
    with (
        patch(
            "homeassistant.components.nintendo_parental.Authenticator",
            autospec=True,
        ) as mock_auth_class,
        patch(
            "homeassistant.components.nintendo_parental.config_flow.Authenticator",
            new=mock_auth_class,
        ),
    ):
        mock_auth = MagicMock()
        mock_auth._id_token = "valid_token"
        mock_auth._at_expiry = datetime(2099, 12, 31, 23, 59, 59)
        mock_auth.account_id = "aabbccddee112233"
        mock_auth.login_url = "http://example.com"
        mock_auth.get_session_token = "valid_token"
        # Patch complete_login as an AsyncMock on both instance and class as this is a class method
        mock_auth.complete_login = AsyncMock()
        type(mock_auth).complete_login = mock_auth.complete_login
        mock_auth_class.generate_login.return_value = mock_auth
        yield mock_auth


@pytest.fixture
def mock_nintendo_client(
    mock_nintendo_device: Device,
) -> Generator[AsyncMock]:
    """Mock a Nintendo client."""
    with (
        patch(
            "homeassistant.components.nintendo_parental.NintendoParental",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.nintendo_parental.config_flow.NintendoParental",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.update.return_value = True
        client.devices.return_value = {"testdevid": mock_nintendo_device}
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.nintendo_parental.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry
