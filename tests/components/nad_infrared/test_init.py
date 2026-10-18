"""Tests for the NAD Infrared integration setup."""

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.nad_infrared.const import CONF_INFRARED_ENTITY_ID
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_INFRARED_EMITTER_ENTITY_ID

from tests.common import MockConfigEntry
from tests.components.infrared.common import MockInfraredEmitterEntity

NEW_EMITTER_ENTITY_ID = "infrared.renamed_ir_emitter"


async def test_setup_and_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test setting up and unloading a config entry."""
    entry = init_integration
    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_emitter_entity_id_renamed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Renaming the emitter reloads the entry and keeps the controls working."""
    entry = init_integration
    stored_emitter = entry.data[CONF_INFRARED_ENTITY_ID]

    entity_registry.async_update_entity(
        MOCK_INFRARED_EMITTER_ENTITY_ID, new_entity_id=NEW_EMITTER_ENTITY_ID
    )
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_INFRARED_ENTITY_ID] == stored_emitter
    assert entry.runtime_data == NEW_EMITTER_ENTITY_ID
    await _assert_button_works(hass, mock_infrared_emitter_entity)


async def test_emitter_renamed_while_entry_disabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """A rename while the entry is disabled is picked up when it is re-enabled."""
    entry = init_integration

    await hass.config_entries.async_set_disabled_by(
        entry.entry_id, ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED

    entity_registry.async_update_entity(
        MOCK_INFRARED_EMITTER_ENTITY_ID, new_entity_id=NEW_EMITTER_ENTITY_ID
    )
    await hass.async_block_till_done()

    await hass.config_entries.async_set_disabled_by(entry.entry_id, None)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data == NEW_EMITTER_ENTITY_ID
    await _assert_button_works(hass, mock_infrared_emitter_entity)


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


async def _assert_button_works(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Assert a button is available and its press reaches the emitter."""
    state = hass.states.get("button.nad_receiver_display")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.nad_receiver_display"},
        blocking=True,
    )
    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
