"""Fixtures for SpaceXAI tests."""

from collections.abc import Generator
import time
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.spacexai.client import (
    AccountInfo,
    ModelInfo,
    ProviderSnapshot,
)
from homeassistant.components.spacexai.const import (
    CONF_MAX_OUTPUT_TOKENS,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_MODEL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_LLM_HASS_API, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from . import EventStream, message_events

from tests.common import MockConfigEntry

ACCOUNT_ID = "account-123"
ACCESS_TOKEN = "access-token"
REFRESH_TOKEN = "refresh-token"


@pytest.fixture
def provider_snapshot() -> ProviderSnapshot:
    """Return a valid provider snapshot."""
    return ProviderSnapshot(
        account=AccountInfo(
            subject=ACCOUNT_ID,
            name="Home User",
            email="home@example.com",
        ),
        models=(
            ModelInfo(id=DEFAULT_MODEL, owner="xai"),
            ModelInfo(id="grok-4.3", owner="xai"),
        ),
    )


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a configured SpaceXAI entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home User",
        unique_id=ACCOUNT_ID,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": ACCESS_TOKEN,
                "refresh_token": REFRESH_TOKEN,
                "expires_at": time.time() + 3600,
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        },
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_MODEL: DEFAULT_MODEL,
                    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
                    CONF_MAX_OUTPUT_TOKENS: DEFAULT_MAX_OUTPUT_TOKENS,
                },
                subentry_type="conversation",
                title="Grok",
                unique_id=None,
            ),
        ],
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_validate(provider_snapshot: ProviderSnapshot) -> Generator[AsyncMock]:
    """Mock provider account validation."""
    with patch(
        "homeassistant.components.spacexai.client.SpaceXAIClient.async_validate",
        new_callable=AsyncMock,
        return_value=provider_snapshot,
    ) as mock:
        yield mock


@pytest.fixture
def mock_stream() -> Generator[AsyncMock]:
    """Mock a successful streaming provider response."""
    with patch(
        "homeassistant.components.spacexai.client.SpaceXAIClient.async_stream_response",
        new_callable=AsyncMock,
        return_value=EventStream(message_events("Hello from Grok")),
    ) as mock:
        yield mock


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_validate: AsyncMock,
    setup_credentials: None,
) -> MockConfigEntry:
    """Set up SpaceXAI."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent config flow tests from setting up a created entry."""
    with patch(
        "homeassistant.components.spacexai.async_setup_entry",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock:
        yield mock


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Register a legitimate test OAuth client identity."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential("home-assistant-client", ""),
        DOMAIN,
    )


@pytest.fixture(autouse=True)
async def setup_homeassistant(hass: HomeAssistant) -> None:
    """Set up the Home Assistant LLM API."""
    assert await async_setup_component(hass, "homeassistant", {})
