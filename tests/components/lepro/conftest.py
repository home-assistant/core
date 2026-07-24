"""Fixtures for Lepro integration tests."""

from __future__ import annotations

from collections.abc import Generator
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.lepro.const import CONF_ACCOUNT, CONF_API_HOST, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_json_object_fixture

CLIENT_ID = "test-client-id"
CLIENT_SECRET = "test-client-secret"
API_HOST = "https://api-us-iot.lepro.com"
ACCOUNT = "user@example.com"


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Set up application credentials for tests."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
        DOMAIN,
    )


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return int(time.time()) + 3600


@pytest.fixture
def mock_config_entry(expires_at: int) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Lepro",
        unique_id=CLIENT_ID,
        data={
            "auth_implementation": DOMAIN,
            CONF_API_HOST: API_HOST,
            CONF_ACCOUNT: ACCOUNT,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "expires_at": float(expires_at),
            },
        },
    )


def _build_devices() -> dict[int, dict[str, Any]]:
    """Build device data dict from fixture."""
    raw = load_json_object_fixture("devices.json", DOMAIN)
    return {d["did"]: d for d in raw["data"]["list"]}


@pytest.fixture
def mock_lepro_api() -> Generator[MagicMock]:
    """Mock the LoproApiClient."""
    with patch(
        "homeassistant.components.lepro.LoproApiClient", autospec=True
    ) as mock_api_class:
        client = mock_api_class.return_value
        client.async_get_devices = AsyncMock(
            return_value=load_json_object_fixture("devices.json", DOMAIN)["data"][
                "list"
            ]
        )
        client.async_turn_on = AsyncMock()
        client.async_turn_off = AsyncMock()
        client.async_set_brightness = AsyncMock()
        client.async_set_color = AsyncMock()
        client.async_set_color_temp = AsyncMock()
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lepro_api: MagicMock,
) -> MockConfigEntry:
    """Set up the Lepro integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.lepro.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ) as mock_impl:
        mock_impl.return_value = MagicMock()
        with patch(
            "homeassistant.components.lepro.config_entry_oauth2_flow.OAuth2Session"
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    return mock_config_entry
