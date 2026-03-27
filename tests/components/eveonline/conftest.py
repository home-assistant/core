"""Fixtures for the Eve Online integration tests."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from eveonline.models import ServerStatus
import pytest

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.eveonline.const import DOMAIN
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
                "token_type": "Bearer",
            },
            "character_id": CHARACTER_ID,
            "character_name": CHARACTER_NAME,
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
        client.async_get_server_status = AsyncMock()
        client.async_get_character_online = AsyncMock(return_value=None)
        client.async_get_wallet_balance = AsyncMock(return_value=None)
        client.async_get_skill_queue = AsyncMock(return_value=[])
        client.async_get_character_location = AsyncMock(return_value=None)
        client.async_get_character_ship = AsyncMock(return_value=None)
        client.async_get_skills = AsyncMock(return_value=None)
        client.async_get_mail_labels = AsyncMock(return_value=None)
        client.async_get_industry_jobs = AsyncMock(return_value=[])
        client.async_get_market_orders = AsyncMock(return_value=[])
        client.async_get_jump_fatigue = AsyncMock(return_value=None)
        client.async_resolve_names = AsyncMock(return_value=[])
        yield client


def mock_server_status(players: int = 25000) -> ServerStatus:
    """Return a mock ServerStatus with all required fields."""
    return ServerStatus(
        players=players,
        server_version="2345678",
        start_time=datetime(2026, 3, 27, 11, 0, 0, tzinfo=UTC),
    )
