"""Tests for the NAD Infrared integration setup."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_INFRARED_EMITTER_ENTITY_ID


async def test_setup_and_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test setting up and unloading a config entry."""
    entry = init_integration
    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_emitter_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Setup fails with a clear error when the emitter no longer exists."""
    entity_registry.async_remove(MOCK_INFRARED_EMITTER_ENTITY_ID)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == "emitter_not_found"
