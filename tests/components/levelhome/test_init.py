"""Tests for the Level Lock integration init/unload."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_unload_entry(hass: HomeAssistant) -> None:
    """Test setting up and unloading a config entry."""

    # Minimal mock config entry with OAuth2 data
    from homeassistant.components.levelhome.const import DOMAIN

    entry = MockConfigEntry(
        domain=DOMAIN, 
        data={
            "auth_implementation": "levelhome",
            "token": {
                "access_token": "test-token",
                "refresh_token": "test-refresh-token",
                "expires_at": 9999999999,
                "expires_in": 3600,
            }
        }, 
        unique_id="test-uid"
    )
    entry.add_to_hass(hass)

    # Create a mock OAuth2 implementation
    from types import SimpleNamespace
    from homeassistant.helpers import config_entry_oauth2_flow
    
    mock_impl = SimpleNamespace(
        domain="levelhome",
        name="Level Lock",
        client_id="test-client-id",
        redirect_uri="https://example.com/redirect",
        extra_token_resolve_data={},
    )

    # Use fakes for Client and WebSocket manager to capture closures and avoid I/O
    class _FakeClient:
        last: object | None = None

        def __init__(self, session, base_url, get_token):
            self.get_token = get_token
            _FakeClient.last = self

        async def async_list_locks_normalized(self):
            return []

        async def async_get_lock_status_bool(self, lock_id):
            return True

        async def async_lock(self, lock_id):
            return None

        async def async_unlock(self, lock_id):
            return None

    class _FakeWS:
        last: object | None = None

        def __init__(self, session, base_url, get_token, on_state_update):
            self.on_state_update = on_state_update
            _FakeWS.last = self

        async def async_start(self, lock_ids):
            return None

        async def async_stop(self):
            return None

    # Patch OAuth token retrieval to avoid touching real OAuth2 machinery
    with (
        patch(
            "homeassistant.components.levelhome.auth.AsyncConfigEntryAuth.async_get_access_token",
            return_value="test-token",
        ),
        # Mock the OAuth2 implementation lookup
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
            return_value=mock_impl,
        ),
        # Skip initial refresh to avoid real HTTP in setup
        patch(
            "homeassistant.components.levelhome.coordinator.LevelLocksCoordinator.async_config_entry_first_refresh",
            new=AsyncMock(return_value=None),
        ),
        # Replace symbols where they are used (aliased in __init__.py)
        patch(
            "homeassistant.components.levelhome.__init__.LibClient",
            new=_FakeClient,
        ),
        patch(
            "homeassistant.components.levelhome.__init__.LevelWebsocketManager",
            new=_FakeWS,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Trigger the captured token provider to cover _get_token in __init__.py
        if _FakeClient.last is not None:
            get_token = getattr(_FakeClient.last, "get_token", None)
            if get_token is not None:
                await get_token()

        # Trigger the captured on_state callback to cover _on_state wrapper in __init__.py
        if _FakeWS.last is not None:
            on_state = getattr(_FakeWS.last, "on_state_update", None)
            if on_state is not None:
                await on_state("lock-id", True, {"state": "locked"})

    assert entry.state is config_entries.ConfigEntryState.LOADED

    # Unload
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED


