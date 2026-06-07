"""Tests for the integration setup / unload lifecycle."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Setting up creates the runtime data; unloading clears it."""
    entry = setup_integration
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not None
    assert entry.runtime_data.client is not None
    assert entry.runtime_data.coordinator is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_options_update_reloads(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Saving options triggers a reload."""
    entry = setup_integration
    with patch(
        "homeassistant.components.culiplan.config_entry_oauth2_flow.OAuth2Session"
    ) as mock_session:
        mock_session.return_value.async_ensure_token_valid = AsyncMock()
        mock_session.return_value.token = {"access_token": "test-access-token"}
        hass.config_entries.async_update_entry(entry, options={"foo": "bar"})
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.options == {"foo": "bar"}
