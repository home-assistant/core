"""Tests for the BenQ Projector Infrared integration setup."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_INFRARED_EMITTER_ENTITY_ID, MOCK_INFRARED_RECEIVER_ENTITY_ID


async def test_setup_and_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test setting up and unloading a config entry."""
    entry = init_integration
    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("removed_entity_id", "translation_key"),
    [
        (MOCK_INFRARED_EMITTER_ENTITY_ID, "emitter_not_found"),
        (MOCK_INFRARED_RECEIVER_ENTITY_ID, "receiver_not_found"),
    ],
)
@pytest.mark.parametrize("has_receiver_entity", [True])
@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_infrared_entity_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    removed_entity_id: str,
    translation_key: str,
) -> None:
    """Setup fails with a clear error when the emitter or receiver no longer exists."""
    entity_registry.async_remove(removed_entity_id)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == translation_key
