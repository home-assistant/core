"""Tests for Google Photos."""

import http
import time

from aiohttp import ClientError
from google_photos_library_api.exceptions import GooglePhotosApiError
import pytest

from homeassistant.components.google_photos.const import OAUTH2_TOKEN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.usefixtures("setup_integration")
async def test_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test successful setup and unload."""
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.fixture(name="refresh_token_status")
def mock_refresh_token_status() -> http.HTTPStatus:
    """Fixture to set a token refresh status."""
    return http.HTTPStatus.OK


@pytest.fixture(name="refresh_token_exception")
def mock_refresh_token_exception() -> Exception | None:
    """Fixture to set a token refresh status."""
    return None


@pytest.fixture(name="refresh_token")
def mock_refresh_token(
    aioclient_mock: AiohttpClientMocker,
    refresh_token_status: http.HTTPStatus,
    refresh_token_exception: Exception | None,
) -> MockConfigEntry:
    """Fixture to simulate a token refresh response."""
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        exc=refresh_token_exception,
        status=refresh_token_status,
        json={
            "access_token": "updated-access-token",
            "refresh_token": "updated-refresh-token",
            "expires_at": time.time() + 3600,
            "expires_in": 3600,
        },
    )


@pytest.mark.usefixtures("refresh_token", "setup_integration")
@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
async def test_expired_token_refresh_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test expired token is refreshed."""
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.data["token"]["access_token"] == "updated-access-token"
    assert config_entry.data["token"]["expires_in"] == 3600


@pytest.mark.usefixtures("refresh_token", "setup_integration")
@pytest.mark.parametrize(
    ("expires_at", "refresh_token_status", "refresh_token_exception", "expected_state"),
    [
        (
            time.time() - 3600,
            http.HTTPStatus.UNAUTHORIZED,
            None,
            ConfigEntryState.SETUP_ERROR,  # Reauth
        ),
        (
            time.time() - 3600,
            http.HTTPStatus.INTERNAL_SERVER_ERROR,
            None,
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            time.time() - 3600,
            None,
            ClientError("Client exception raised"),
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    ids=["unauthorized", "internal_server_error", "client_error"],
)
async def test_expired_token_refresh_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    expected_state: ConfigEntryState,
) -> None:
    """Test failure while refreshing token with a transient error."""

    assert config_entry.state is expected_state


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize("api_error", [GooglePhotosApiError("some error")])
async def test_coordinator_init_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test init failure to load albums."""
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
