"""Fixtures for the Eve Online integration tests."""

from collections.abc import Generator
import time
from unittest.mock import AsyncMock, patch

from eveonline.models import CharacterOnlineStatus
import pytest

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.eveonline.const import (
    CONF_CHARACTER_ID,
    CONF_CHARACTER_NAME,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

CLIENT_ID = "test-client-id"
CLIENT_SECRET = "test-client-secret"
CHARACTER_ID = 12345678
CHARACTER_NAME = "Test Capsuleer"


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to set up application credentials."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=CHARACTER_NAME,
        unique_id=str(CHARACTER_ID),
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_in": 1200,
                "expires_at": time.time() + 1200,
                "token_type": "Bearer",
            },
            CONF_CHARACTER_ID: CHARACTER_ID,
            CONF_CHARACTER_NAME: CHARACTER_NAME,
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_eveonline_client() -> Generator[AsyncMock]:
    """Mock the EveOnlineClient."""
    with patch(
        "homeassistant.components.eveonline.EveOnlineClient",
        autospec=True,
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.async_get_character_online.return_value = CharacterOnlineStatus(
            online=True
        )
        client.async_get_wallet_balance.return_value = None
        client.async_get_skill_queue.return_value = []
        client.async_get_character_location.return_value = None
        client.async_get_character_ship.return_value = None
        client.async_get_skills.return_value = None
        client.async_get_mail_labels.return_value = None
        client.async_get_industry_jobs.return_value = []
        client.async_get_market_orders.return_value = []
        client.async_get_jump_fatigue.return_value = None
        client.async_resolve_names.return_value = []
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> MockConfigEntry:
    """Set up the Eve Online integration."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    return mock_config_entry
