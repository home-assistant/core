"""Test fixtures for Google Tasks."""

from collections.abc import Awaitable, Callable
import json
import time
from typing import Any
from unittest.mock import Mock, patch

from httplib2 import Response
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.google_tasks.const import DOMAIN, OAUTH2_SCOPES
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
FAKE_ACCESS_TOKEN = "some-access-token"
FAKE_REFRESH_TOKEN = "some-refresh-token"
FAKE_AUTH_IMPL = "conftest-imported-cred"

TASK_LIST = {
    "id": "task-list-id-1",
    "title": "My tasks",
}
LIST_TASK_LIST_RESPONSE = {
    "items": [TASK_LIST],
}

LIST_TASKS_RESPONSE_WATER = {
    "items": [
        {
            "id": "some-task-id",
            "title": "Water",
            "status": "needsAction",
            "description": "Any size is ok",
            "position": "00000000000000000001",
        },
    ],
}


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return []


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 86400


@pytest.fixture(name="token_entry")
def mock_token_entry(expires_at: int) -> dict[str, Any]:
    """Fixture for OAuth 'token' data for a ConfigEntry."""
    return {
        "access_token": FAKE_ACCESS_TOKEN,
        "refresh_token": FAKE_REFRESH_TOKEN,
        "scope": " ".join(OAUTH2_SCOPES),
        "token_type": "Bearer",
        "expires_at": expires_at,
    }


@pytest.fixture(name="config_entry")
def mock_config_entry(token_entry: dict[str, Any]) -> MockConfigEntry:
    """Fixture for a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="123",
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
        },
    )


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.fixture(name="integration_setup")
async def mock_integration_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    platforms: list[str],
) -> Callable[[], Awaitable[bool]]:
    """Fixture to set up the integration."""
    config_entry.add_to_hass(hass)

    async def run() -> bool:
        with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", platforms):
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()
        return result

    return run


@pytest.fixture(name="api_responses")
def mock_api_responses() -> list[dict | list]:
    """Fixture forcreate_response_object API responses to return during test."""
    return []


def create_response_object(api_response: dict | list) -> tuple[Response, bytes]:
    """Create an http response."""
    return (
        Response({"Content-Type": "application/json"}),
        json.dumps(api_response).encode(),
    )


@pytest.fixture(name="response_handler")
def mock_response_handler(api_responses: list[dict | list]) -> list:
    """Create a mock http2lib response handler."""
    return [create_response_object(api_response) for api_response in api_responses]


@pytest.fixture
def mock_http_response(response_handler: list | Callable) -> Mock:
    """Fixture to fake out http2lib responses."""

    with patch("httplib2.Http.request", side_effect=response_handler) as mock_response:
        yield mock_response
