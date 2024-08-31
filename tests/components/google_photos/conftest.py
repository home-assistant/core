"""Test fixtures for Google Photos."""

from collections.abc import Awaitable, Callable, Generator
import time
from typing import Any
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.google_photos.const import DOMAIN, OAUTH2_SCOPES
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_json_array_fixture

USER_IDENTIFIER = "user-identifier-1"
CONFIG_ENTRY_ID = "user-identifier-1"
CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
FAKE_ACCESS_TOKEN = "some-access-token"
FAKE_REFRESH_TOKEN = "some-refresh-token"
EXPIRES_IN = 3600


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return time.time() + EXPIRES_IN


@pytest.fixture(name="token_entry")
def mock_token_entry(expires_at: int) -> dict[str, Any]:
    """Fixture for OAuth 'token' data for a ConfigEntry."""
    return {
        "access_token": FAKE_ACCESS_TOKEN,
        "refresh_token": FAKE_REFRESH_TOKEN,
        "scope": " ".join(OAUTH2_SCOPES),
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


@pytest.fixture(name="setup_api")
def mock_setup_api(
    fixture_name: str, user_identifier: str
) -> Generator[Mock, None, None]:
    """Set up fake Google Photos API responses from fixtures."""
    with patch("homeassistant.components.google_photos.api.build") as mock:
        mock.return_value.userinfo.return_value.get.return_value.execute.return_value = {
            "id": user_identifier,
            "name": "Test Name",
        }

        responses = (
            load_json_array_fixture(fixture_name, DOMAIN) if fixture_name else []
        )

        queue = list(responses)

        def list_media_items(**kwargs: Any) -> Mock:
            mock = Mock()
            mock.execute.return_value = queue.pop(0)
            return mock

        mock.return_value.mediaItems.return_value.list = list_media_items

        # Mock a point lookup by reading contents of the fixture above
        def get_media_item(mediaItemId: str, **kwargs: Any) -> Mock:
            for response in responses:
                for media_item in response["mediaItems"]:
                    if media_item["id"] == mediaItemId:
                        mock = Mock()
                        mock.execute.return_value = media_item
                        return mock
            return None

        mock.return_value.mediaItems.return_value.get = get_media_item
        yield mock


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> Callable[[], Awaitable[bool]]:
    """Fixture to set up the integration."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
