"""Fixtures for Gentex HomeLink tests."""

from collections.abc import Generator
from http import HTTPStatus
from unittest.mock import AsyncMock, patch

from homelink.model.button import Button
import homelink.model.device
import pytest

from homeassistant.components.gentex_homelink.const import DOMAIN, OAUTH2_TOKEN_URL

from . import TEST_ACCESS_JWT, TEST_UNIQUE_ID

from tests.common import MockConfigEntry
from tests.conftest import AiohttpClientMocker


@pytest.fixture
def mock_srp_access_token() -> str:
    """Return preferred JWT for mock SRP auth requests."""
    return TEST_ACCESS_JWT


@pytest.fixture
def mock_srp_auth(mock_srp_access_token: str) -> Generator[AsyncMock]:
    """Mock SRP authentication."""
    with patch(
        "homeassistant.components.gentex_homelink.config_flow.SRPAuth"
    ) as mock_srp_auth:
        instance = mock_srp_auth.return_value
        instance.async_get_access_token.return_value = {
            "AuthenticationResult": {
                "AccessToken": mock_srp_access_token,
                "RefreshToken": "refresh",
                "TokenType": "bearer",
                "ExpiresIn": 3600,
            }
        }
        yield instance


@pytest.fixture
def aioclient_mock_fixture(aioclient_mock: AiohttpClientMocker) -> None:
    """Fixture to provide a aioclient mocker."""
    aioclient_mock.post(OAUTH2_TOKEN_URL, status=HTTPStatus.OK, json={})


@pytest.fixture
def mock_mqtt_provider(mock_device: AsyncMock) -> Generator[AsyncMock]:
    """Mock MQTT provider."""
    with patch(
        "homeassistant.components.gentex_homelink.MQTTProvider", autospec=True
    ) as mock_mqtt_provider:
        instance = mock_mqtt_provider.return_value
        instance.discover.return_value = [mock_device]
        yield instance


@pytest.fixture
def mock_device() -> AsyncMock:
    """Mock Device instance."""
    device = AsyncMock(spec=homelink.model.device.Device, autospec=True)
    buttons = [
        Button(id="1", name="Button 1", device=device),
        Button(id="2", name="Button 2", device=device),
        Button(id="3", name="Button 3", device=device),
    ]
    device.id = "TestDevice"
    device.name = "TestDevice"
    device.buttons = buttons
    return device


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock setup entry."""
    return MockConfigEntry(
        unique_id=TEST_UNIQUE_ID,
        version=1,
        domain=DOMAIN,
        data={
            "auth_implementation": "gentex_homelink",
            "token": {
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_in": 3600,
                "token_type": "bearer",
                "expires_at": 1234567890,
            },
        },
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setup entry."""
    with patch(
        "homeassistant.components.gentex_homelink.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
