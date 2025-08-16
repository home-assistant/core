"""Common fixtures for the Nintendo Switch Parental Controls tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pynintendoparental import Device
import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.nintendo_parental.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_nintendo_client_init() -> Generator[MagicMock]:
    """Return a mocked NintendoParental."""
    with (
        patch(
            "homeassistant.components.nintendo_parental.config_flow.NintendoParental",
            autospec=True,
        ) as nintendo_parental_client,
        patch(
            "homeassistant.components.nintendo_parental.NintendoParental",
            new=nintendo_parental_client,
        ),
    ):
        yield nintendo_parental_client


@pytest.fixture
def mock_request_handler() -> Generator[MagicMock]:
    """Mock the _request_handler function."""
    with patch(
        "pynintendoparental.authenticator.Authenticator._request_handler",
        autospec=True,
    ) as mock_request:
        # Define a mocked response
        mock_request.return_value = {
            "status": 200,
            "text": "OK",
            "json": {
                "session_token": "valid_token",
                "expires_in": 3500,
                "id": "aabbccddee112233",
                "name": "Home Assistant Tester",
            },
            "headers": {"Content-Type": "application/json"},
        }
        yield mock_request


@pytest.fixture
def mock_authenticator_client(mock_request_handler: MagicMock) -> Generator[MagicMock]:
    """Mock a Nintendo authenticator."""
    with (
        patch(
            "pynintendoparental.authenticator.Authenticator",
            autospec=True,
        ) as mock_nintendo_auth,
        patch(
            "pynintendoparental.authenticator._parse_response_token",
            autospec=True,
        ) as mock_parse_response_token,
    ):
        mock_nintendo_auth.return_value = mock_nintendo_auth
        mock_nintendo_auth.perform_login.return_value = True
        mock_nintendo_auth.get_session_token.return_value = "npf54789befxxxxxxxx://auth#session_token_code=valid_token&state=valid_state&session_state=valid_session_state"
        mock_nintendo_auth.perform_refresh.return_value = True
        mock_nintendo_auth.account_id = "aabbccddee112233"
        mock_nintendo_auth._request_handler = mock_request_handler
        # Mock the response of _parse_response_token
        mock_parse_response_token.return_value = {
            "session_token_code": "valid_token",
            "state": "valid_state",
            "session_state": "valid_session_state",
        }

        yield mock_nintendo_auth


@pytest.fixture
def mock_nintendo_device() -> Generator[MagicMock]:
    """Mock a single device."""
    with patch(
        "pynintendoparental.device.Device", autospec=True, return_value=True
    ) as mock_nintendo_device:
        mock_nintendo_device.device_id.return_value = "testdevid"
        mock_nintendo_device.name.return_value = "Home Assistant Test"
        mock_nintendo_device.extra.return_value = {
            "device": {"firmwareVersion": {"displayedVersion": "99.99.99"}}
        }
        mock_nintendo_device.limit_time.return_value = 120
        mock_nintendo_device.today_playing_time.return_value = 110
        yield mock_nintendo_device


@pytest.fixture
def mock_nintendo_devices(mock_nintendo_device: MagicMock) -> dict[str, Device]:
    """Mock a collection of devices."""
    return {"testdevid": mock_nintendo_device}


@pytest.fixture
def mock_nintendo_client(
    mock_nintendo_client_init: MagicMock,
    mock_nintendo_devices: MagicMock,
    mock_authenticator_client: MagicMock,
) -> Generator[AsyncMock]:
    """Mock a Nintendo client."""
    client = mock_nintendo_client_init.return_value
    client.update.return_value = True
    client.devices.return_value = mock_nintendo_devices.return_value
    return client
