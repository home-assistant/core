"""Tests for the NAD Infrared integration setup."""

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.nad_infrared.const import CONF_INFRARED_ENTITY_ID
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_INFRARED_EMITTER_ENTITY_ID

from tests.common import MockConfigEntry
from tests.components.infrared.common import MockInfraredEmitterEntity


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
    """Renaming the emitter updates the entry and keeps the controls working."""
    entry = init_integration
    new_emitter_entity_id = "infrared.renamed_ir_emitter"

    entity_registry.async_update_entity(
        MOCK_INFRARED_EMITTER_ENTITY_ID, new_entity_id=new_emitter_entity_id
    )
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_INFRARED_ENTITY_ID] == new_emitter_entity_id

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
