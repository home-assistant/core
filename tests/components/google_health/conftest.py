"""Test fixtures for Google Health."""

from collections.abc import Awaitable, Callable
import time
from typing import Any

import pytest

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.google_health.const import DOMAIN, OAUTH_SCOPES
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
FAKE_ACCESS_TOKEN = "some-access-token"
FAKE_REFRESH_TOKEN = "some-refresh-token"

API_BASE_URL = "https://health.googleapis.com/v4/users/me"
SETTINGS_URL = f"{API_BASE_URL}/settings"
IDENTITY_URL = f"{API_BASE_URL}/identity"
ROLLUP_URL = f"{API_BASE_URL}/dataTypes/steps/dataPoints:dailyRollUp"


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return int(time.time() + 86400)


@pytest.fixture(name="token_entry")
def mock_token_entry(expires_at: int) -> dict[str, Any]:
    """Fixture for OAuth 'token' data for a ConfigEntry."""
    return {
        "access_token": FAKE_ACCESS_TOKEN,
        "refresh_token": FAKE_REFRESH_TOKEN,
        "scope": " ".join(OAUTH_SCOPES),
        "token_type": "Bearer",
        "expires_at": expires_at,
    }


@pytest.fixture(name="config_entry")
def mock_config_entry(token_entry: dict[str, Any]) -> MockConfigEntry:
    """Fixture for a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="mock-health-user-id",
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
        },
    )


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.fixture(name="integration_setup")
async def mock_integration_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    setup_credentials: None,
) -> Callable[[], Awaitable[bool]]:
    """Fixture to set up the integration."""
    config_entry.add_to_hass(hass)

    async def run() -> bool:
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        return result

    return run
