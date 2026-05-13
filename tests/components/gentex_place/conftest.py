"""Fixtures for Gentex Place tests."""

from collections.abc import Generator
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from place.config import OAUTH2_TOKEN_URL
from place.models import Credentials
from place.models.discover_device import DiscoverDevice
import pytest

from homeassistant.components.gentex_place.const import DOMAIN

from . import TEST_ACCESS_JWT, TEST_UNIQUE_ID

from tests.common import MockConfigEntry
from tests.conftest import AiohttpClientMocker

MOCK_SHADOW = {
    "coAlarmStatus": 0,
    "heatAlarmStatus": 0,
    "smokeAlarmStatus": 0,
    "temperatureC": 22.5,
    "humidity": 45,
    "batteryStatus": 0,
}


@pytest.fixture
def mock_srp_access_token() -> str:
    """Return preferred JWT for mock SRP auth requests."""
    return TEST_ACCESS_JWT


@pytest.fixture
def mock_login(mock_srp_access_token: str) -> Generator[MagicMock]:
    """Mock the place SRP login function."""
    with patch("homeassistant.components.gentex_place.config_flow.login") as mock_login:
        mock_login.return_value = {
            "AuthenticationResult": {
                "AccessToken": mock_srp_access_token,
                "IdToken": "mock-id-token",
                "RefreshToken": "refresh",
                "TokenType": "bearer",
                "ExpiresIn": 3600,
            }
        }
        yield mock_login


@pytest.fixture
def aioclient_mock_fixture(aioclient_mock: AiohttpClientMocker) -> None:
    """Fixture to provide an aioclient mocker."""
    aioclient_mock.post(OAUTH2_TOKEN_URL, status=HTTPStatus.OK, json={})


@pytest.fixture
def mock_provider(mock_discover_device: DiscoverDevice) -> Generator[AsyncMock]:
    """Mock Place Provider."""
    with patch(
        "homeassistant.components.gentex_place.Provider", autospec=True
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.enable = AsyncMock(return_value={"success": True})
        instance.discover = AsyncMock(return_value=[mock_discover_device])
        yield instance


@pytest.fixture
def mock_discover_device() -> DiscoverDevice:
    """Mock DiscoverDevice instance."""
    return DiscoverDevice(
        location="Master Bedroom",
        shadow=MOCK_SHADOW,
        device_name="Test Detector",
        thing_name="thing-001",
        firmware_version="1.0.0",
        model_number="MODEL-X",
        device_id="device-001",
        online=True,
    )


@pytest.fixture
def mock_credentials() -> Credentials:
    """Mock AWS IoT Credentials."""
    return Credentials(
        access_key_id="AKID",
        secret_access_key="secret",
        session_token="session",
        identity_id="us-east-2:identity-id",
        access_token="mock-access-token",
    )


@pytest.fixture
def mock_get_iot_credentials(mock_credentials: Credentials) -> Generator[MagicMock]:
    """Mock the get_iot_credentials function."""
    with patch(
        "homeassistant.components.gentex_place.get_iot_credentials",
        return_value=mock_credentials,
    ) as mock_fn:
        yield mock_fn


@pytest.fixture
def mock_mqtt_client() -> Generator[MagicMock]:
    """Mock Place MqttClient."""
    with patch(
        "homeassistant.components.gentex_place.MqttClient", autospec=True
    ) as mock_cls:
        instance = mock_cls.return_value
        # Provide a mock _client for loop_start/loop_stop
        instance._client = MagicMock()
        yield instance


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock config entry with stored tokens."""
    return MockConfigEntry(
        unique_id=TEST_UNIQUE_ID,
        version=1,
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "refresh",
                "id_token": "mock-id-token",
                "expires_in": 3600,
                "token_type": "bearer",
                "expires_at": 9999999999,
            },
        },
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock async_setup_entry and async_unload_entry."""
    with (
        patch(
            "homeassistant.components.gentex_place.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.gentex_place.async_unload_entry",
            return_value=True,
        ),
    ):
        yield mock_setup_entry
