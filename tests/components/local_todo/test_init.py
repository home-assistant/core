"""Tests for init platform of local_todo."""

from unittest.mock import patch

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import TEST_ENTITY

from tests.common import MockConfigEntry


async def test_load_unload(
    hass: HomeAssistant, setup_integration: None, config_entry: MockConfigEntry
) -> None:
    """Test loading and unloading a config entry."""

    assert config_entry.state == ConfigEntryState.LOADED

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "0"

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "unavailable"


async def test_remove_config_entry(
    hass: HomeAssistant, setup_integration: None, config_entry: MockConfigEntry
) -> None:
    """Test removing a config entry."""

    with patch("homeassistant.components.local_todo.Path.unlink") as unlink_mock:
        assert await hass.config_entries.async_remove(config_entry.entry_id)
        await hass.async_block_till_done()
        unlink_mock.assert_called_once()


@pytest.mark.parametrize(
    ("store_read_side_effect"),
    [
        (OSError("read error")),
    ],
)
async def test_load_failure(
    hass: HomeAssistant, setup_integration: None, config_entry: MockConfigEntry
) -> None:
    """Test failures loading the todo store."""

    assert config_entry.state == ConfigEntryState.SETUP_RETRY

    state = hass.states.get(TEST_ENTITY)
    assert not state
