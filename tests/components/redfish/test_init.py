"""Tests for Redfish config-entry lifecycle."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_redfish_api: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock],
) -> None:
    """Test all platforms set up and unload cleanly."""
    assert init_integration.state is ConfigEntryState.LOADED
    mock_redfish_api[2].assert_awaited_once_with()

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    entry = hass.config_entries.async_get_entry(init_integration.entry_id)
    assert entry is not None
    assert entry.state is ConfigEntryState.NOT_LOADED
    mock_redfish_api[3].assert_awaited_once_with()


async def test_unload_failure_does_not_logout(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_redfish_api: tuple[AsyncMock, AsyncMock, AsyncMock, AsyncMock],
) -> None:
    """Test authentication remains active when platform unload fails."""
    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new=AsyncMock(return_value=False),
    ):
        assert not await hass.config_entries.async_unload(init_integration.entry_id)

    mock_redfish_api[3].assert_not_awaited()
