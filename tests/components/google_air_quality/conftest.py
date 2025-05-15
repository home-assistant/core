"""Test fixtures for Google Photos."""

from collections.abc import Awaitable, Callable, Generator
import time
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from google_air_quality_api.api import GoogleAirQualityApi
from google_air_quality_api.model import AirQualityData, UserInfoResult
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.google_air_quality.const import DOMAIN, OAUTH2_SCOPES
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_json_object_fixture

USER_IDENTIFIER = "user-identifier-1"
CONFIG_ENTRY_ID = "user-identifier-1"
CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
FAKE_ACCESS_TOKEN = "some-access-token"
FAKE_REFRESH_TOKEN = "some-refresh-token"
EXPIRES_IN = 3600
USERINFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"
PHOTOS_BASE_URL = "https://photoslibrary.googleapis.com"
MEDIA_ITEMS_URL = f"{PHOTOS_BASE_URL}/v1/mediaItems"


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return time.time() + EXPIRES_IN


@pytest.fixture(name="scopes")
def mock_scopes() -> list[str]:
    """Fixture to set scopes used during the config entry."""
    return OAUTH2_SCOPES


@pytest.fixture(name="token_entry")
def mock_token_entry(expires_at: int, scopes: list[str]) -> dict[str, Any]:
    """Fixture for OAuth 'token' data for a ConfigEntry."""
    return {
        "access_token": FAKE_ACCESS_TOKEN,
        "refresh_token": FAKE_REFRESH_TOKEN,
        "scope": " ".join(scopes),
        "type": "Bearer",
        "expires_at": expires_at,
        "expires_in": EXPIRES_IN,
    }


@pytest.fixture(name="config_entry_id")
def mock_config_entry_id() -> str | None:
    """Provide a json fixture file to load for list media item api responses."""
    return CONFIG_ENTRY_ID


@pytest.fixture(name="config_entry")
def mock_config_entry(
    config_entry_id: str, token_entry: dict[str, Any]
) -> MockConfigEntry:
    """Fixture for a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=config_entry_id,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
        },
        title="Account Name",
    )


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.fixture(name="fixture_name")
def mock_fixture_name() -> str | None:
    """Provide a json fixture file to load for list media item api responses."""
    return None


@pytest.fixture(name="user_identifier")
def mock_user_identifier() -> str | None:
    """Provide a json fixture file to load for list media item api responses."""
    return USER_IDENTIFIER


@pytest.fixture(name="api_error")
def mock_api_error() -> Exception | None:
    """Provide a json fixture file to load for list media item api responses."""
    return None


# @pytest.fixture(name="mock_api")
# def mock_client_api(
#     fixture_name: str | None,
#     user_identifier: str,
#     api_error: Exception,
# ) -> Generator[Mock]:
#     """Set up fake Google Photos API responses from fixtures."""
#     mock_api = AsyncMock(spec=GoogleAirQualityApi, autospec=True)

#     # user_identifier, api_error wie gehabt …
#     # Fixture-Name nur nutzen, wenn vorhanden:
#     if fixture_name:
#         responses = load_json_object_fixture(fixture_name, DOMAIN)
#     else:
#         responses = load_json_object_fixture("air_quality_data.json", DOMAIN)

#     if api_error:
#         mock_api.async_air_quality.side_effect = api_error
#     else:
#         mock_api.async_air_quality.return_value = AirQualityData.from_dict(responses)

#     mock_api.get_user_info.return_value = UserInfoResult(
#         id=user_identifier,
#         name="Test Name",
#     )

#     yield mock_api

#     return mock_api


@pytest.fixture(name="mock_api")
def mock_client_api(
    fixture_name: str,
    user_identifier: str,
    api_error: Exception,
) -> Generator[Mock]:
    """Set up fake Google Photos API responses from fixtures."""
    mock_api = AsyncMock(GoogleAirQualityApi, autospec=True)
    mock_api.get_user_info.return_value = UserInfoResult(
        id=user_identifier,
        name="Test Name",
    )
    # responses = (
    #     load_json_object_fixture(fixture_name, DOMAIN)
    #     if fixture_name
    #     else load_json_object_fixture("air_quality_data.json", DOMAIN)
    # )
    responses = load_json_object_fixture("air_quality_data.json", DOMAIN)
    mock_api.async_air_quality.return_value = AirQualityData.from_dict(responses)
    mock_api.async_air_quality.side_effect = api_error

    return mock_api


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api: Mock,
) -> Callable[[], Awaitable[bool]]:
    """Fixture to set up the integration."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.google_air_quality.GoogleAirQualityApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
