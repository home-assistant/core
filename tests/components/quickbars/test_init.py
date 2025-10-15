"""Tests for QuickBars setup, unload, and removal behavior."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_and_unload_entry(
    hass: HomeAssistant, setup_integration, mock_bus_unsub
) -> None:
    """Integration loads & unloads cleanly and cancels the bus listener."""
    entry = setup_integration
    assert entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.NOT_LOADED

    # unsub called once on unload
    mock_bus_unsub.assert_called_once()


async def test_remove_entry_posts_notification(
    hass: HomeAssistant, setup_integration, mock_persistent_notification
) -> None:
    """Deleting an entry shows the reminder via persistent_notification."""
    entry = setup_integration
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert mock_persistent_notification.call_count == 1
    args, kwargs = mock_persistent_notification.call_args
    # Body is second positional arg in async_create(hass, message, title=...)
    message = args[1] if len(args) >= 2 else kwargs.get("message")
    assert "QuickBars" in (message or "")
