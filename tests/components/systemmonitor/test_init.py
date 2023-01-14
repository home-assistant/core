"""Test Systemmonitor component setup process."""
from __future__ import annotations

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Test setup entry."""

    assert loaded_entry.state == config_entries.ConfigEntryState.LOADED


async def test_unload_entry(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Test unload an entry."""

    assert loaded_entry.state == config_entries.ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()
    assert loaded_entry.state is config_entries.ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "get_config",
    [{"sensor": []}],
)
async def test_setup_entry_no_sensors(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test setup entry."""

    assert loaded_entry.state == config_entries.ConfigEntryState.LOADED
    assert len(hass.states.async_all()) == 0
