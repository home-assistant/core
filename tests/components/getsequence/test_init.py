"""Test the Sequence integration __init__.py entry points."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.getsequence import (
    PLATFORMS,
    async_reload_entry,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_async_setup_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test async_setup_entry sets up coordinator and platforms."""
    hass = MagicMock(spec=HomeAssistant)
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.unique_id = "test_unique_id"
    entry.data = {"access_token": "token"}
    entry.runtime_data = None
    entry.add_update_listener = MagicMock()
    entry.async_on_unload = MagicMock()

    # Patch async_get_clientsession and SequenceDataUpdateCoordinator
    monkeypatch.setattr(
        "homeassistant.components.getsequence.async_get_clientsession",
        lambda hass: "session",
    )

    class DummyCoordinator:
        async def async_config_entry_first_refresh(self):
            return True

    monkeypatch.setattr(
        "homeassistant.components.getsequence.SequenceDataUpdateCoordinator",
        lambda hass, entry, session, update_interval: DummyCoordinator(),
    )
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

    result = await async_setup_entry(hass, entry)
    assert result is True
    assert entry.runtime_data is not None
    entry.async_on_unload.assert_called()
    entry.add_update_listener.assert_called()
    hass.config_entries.async_forward_entry_setups.assert_awaited_with(entry, PLATFORMS)


@pytest.mark.asyncio
async def test_async_reload_entry() -> None:
    """Test async_reload_entry calls reload on config entry."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config_entries.async_reload = AsyncMock()
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    await async_reload_entry(hass, entry)
    hass.config_entries.async_reload.assert_awaited_with("test_entry_id")


@pytest.mark.asyncio
async def test_async_unload_entry() -> None:
    """Test async_unload_entry calls unload platforms and returns result."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    entry = MagicMock(spec=ConfigEntry)
    result = await async_unload_entry(hass, entry)
    hass.config_entries.async_unload_platforms.assert_awaited_with(entry, PLATFORMS)
    assert result is True
