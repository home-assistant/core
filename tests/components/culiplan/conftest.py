"""Pytest fixtures for the Culiplan integration tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.culiplan.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.culiplan import CLIENT_ID, CLIENT_SECRET


@pytest.fixture
async def application_credentials(hass: HomeAssistant) -> None:
    """Set up the application_credentials platform with a Culiplan client."""
    assert await async_setup_component(hass, "application_credentials", {})

    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a Culiplan config entry pre-loaded with OAuth tokens."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Culiplan",
        unique_id="user-123",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
                "expires_at": 9_999_999_999,
                "expires_in": 3600,
                "type": "Bearer",
                "issued_at": 1_700_000_000,
            },
        },
    )


@pytest.fixture
def mock_api() -> Generator[AsyncMock]:
    """Return a patched ``CuliplanApiClient`` instance."""
    with patch(
        "homeassistant.components.culiplan.CuliplanApiClient", autospec=True
    ) as cls:
        instance = cls.return_value
        instance.set_access_token = lambda token: None
        instance.async_get_meal_plans = AsyncMock(
            return_value=[
                {
                    "id": "current",
                    "name": "Meal Plan",
                    "slots": [
                        {
                            "id": "slot-1",
                            "date": "2099-01-15T18:00:00Z",
                            "title": "Spaghetti Bolognese",
                            "course": "dinner",
                            "recipeId": "recipe-1",
                            "servings": 2,
                        }
                    ],
                }
            ]
        )
        instance.async_get_shopping_lists = AsyncMock(
            return_value=[
                {
                    "id": "default",
                    "name": "Shopping List",
                    "items": [
                        {"id": "item-1", "name": "Milk", "completed": False},
                        {"id": "item-2", "name": "Bread", "completed": True},
                    ],
                }
            ]
        )
        instance.async_get_pantry_items = AsyncMock(return_value=[])
        instance.async_add_shopping_item = AsyncMock(
            return_value={"id": "new-item", "name": "Eggs"}
        )
        instance.async_update_shopping_item = AsyncMock(return_value={})
        instance.async_remove_shopping_item = AsyncMock(return_value=None)
        instance.async_get_user = AsyncMock(return_value={"id": "user-123"})
        yield instance


@pytest.fixture
def mock_socketio() -> Generator[AsyncMock]:
    """Stub out ``socketio.AsyncClient`` so coordinator.start() is a no-op."""
    with patch(
        "homeassistant.components.culiplan.coordinator.socketio.AsyncClient"
    ) as cls:
        instance = cls.return_value
        instance.connect = AsyncMock()
        instance.disconnect = AsyncMock()
        instance.event = lambda *args, **kwargs: lambda fn: fn
        instance.on = lambda *args, **kwargs: lambda fn: fn
        yield instance


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    application_credentials: None,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
    mock_socketio: AsyncMock,
) -> AsyncGenerator[MockConfigEntry]:
    """Set up the integration with mocked external surfaces."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.culiplan.config_entry_oauth2_flow.OAuth2Session"
    ) as mock_session:
        mock_session.return_value.async_ensure_token_valid = AsyncMock()
        mock_session.return_value.token = {"access_token": "test-access-token"}
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        yield mock_config_entry
