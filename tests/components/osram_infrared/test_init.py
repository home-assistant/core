"""Tests for the OSRAM Infrared integration setup."""

import pytest

from homeassistant.components.osram_infrared.const import (
    CONF_IR_EMITTER_ENTITY_ID,
    CONF_IR_RECEIVER_ENTITY_ID,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.infrared import (
    EMITTER_ENTITY_ID as MOCK_INFRARED_EMITTER_ENTITY_ID,
    RECEIVER_ENTITY_ID as MOCK_INFRARED_RECEIVER_ENTITY_ID,
)


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test setting up and unloading a config entry."""
    entry = init_integration

    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity",
    "mock_infrared_receiver_entity",
    "mock_osram_light_code_to_command",
)
async def test_migrate_v1_to_v2(
    hass: HomeAssistant,
) -> None:
    """Test migration from v1 legacy unique ID to v2 without unique ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id=f"osram_ir_light_{MOCK_INFRARED_EMITTER_ENTITY_ID}",
        data={
            CONF_IR_EMITTER_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
            CONF_IR_RECEIVER_ENTITY_ID: MOCK_INFRARED_RECEIVER_ENTITY_ID,
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.unique_id is None
