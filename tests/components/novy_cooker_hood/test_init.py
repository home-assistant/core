"""Tests for the Novy Cooker Hood integration setup."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.novy_cooker_hood.const import CONF_TRANSMITTER, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import TRANSMITTER_ENTITY_ID

UNKNOWN_TRANSMITTER_UUID = "0123456789abcdef0123456789abcdef"


@pytest.mark.usefixtures("mock_rf_entity")
async def test_migrate_transmitter_uuid_to_entity_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test migrating the stored transmitter UUID to its entity ID."""
    entity_entry = entity_registry.async_get(TRANSMITTER_ENTITY_ID)
    assert entity_entry is not None
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Novy Cooker Hood",
        data={CONF_TRANSMITTER: entity_entry.id, CONF_CODE: 1},
        unique_id=f"{entity_entry.id}_1",
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 1
    assert entry.minor_version == 2
    assert entry.data == {CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID, CONF_CODE: 1}
    assert entry.unique_id == f"{entity_entry.id}_1"


async def test_migrate_unknown_transmitter(hass: HomeAssistant) -> None:
    """Test migration fails when the stored transmitter UUID is unknown."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Novy Cooker Hood",
        data={CONF_TRANSMITTER: UNKNOWN_TRANSMITTER_UUID, CONF_CODE: 1},
        unique_id=f"{UNKNOWN_TRANSMITTER_UUID}_1",
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert entry.minor_version == 1
    assert entry.data == {CONF_TRANSMITTER: UNKNOWN_TRANSMITTER_UUID, CONF_CODE: 1}
