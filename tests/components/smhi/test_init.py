"""Test SMHI component setup process."""

from pysmhi import SMHIPointForecast

from homeassistant.components.smhi.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import ENTITY_ID, TEST_CONFIG, TEST_CONFIG_MIGRATE

from tests.common import MockConfigEntry


async def test_load_and_unload_config_entry(
    hass: HomeAssistant, load_int: MockConfigEntry
) -> None:
    """Test remove entry."""

    assert load_int.state is ConfigEntryState.LOADED
    state = hass.states.get(ENTITY_ID)
    assert state

    await hass.config_entries.async_unload(load_int.entry_id)
    await hass.async_block_till_done()

    assert load_int.state is ConfigEntryState.NOT_LOADED
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE


async def test_migrate_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: SMHIPointForecast,
) -> None:
    """Test migrate entry data."""

    entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG_MIGRATE)
    entry.add_to_hass(hass)
    assert entry.version == 1

    entity = entity_registry.async_get_or_create(
        domain="weather",
        config_entry=entry,
        original_name="Weather",
        platform="smhi",
        supported_features=0,
        unique_id="59.32624, 17.84197",
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)
    assert state

    assert entry.version == 3
    assert entry.unique_id == "59.32624-17.84197"
    assert entry.data == TEST_CONFIG

    entity_get = entity_registry.async_get(entity.entity_id)
    assert entity_get.unique_id == "59.32624, 17.84197"


async def test_migrate_from_future_version(
    hass: HomeAssistant, mock_client: SMHIPointForecast
) -> None:
    """Test migrate entry not possible from future version."""
    entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG_MIGRATE, version=4)
    entry.add_to_hass(hass)
    assert entry.version == 4

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.MIGRATION_ERROR
