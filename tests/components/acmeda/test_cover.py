"""Define tests for the Acmeda config flow."""

from unittest.mock import AsyncMock, patch

import aiopulse
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.acmeda.const import DOMAIN
from homeassistant.components.cover import ATTR_CURRENT_POSITION, DOMAIN as COVER_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.mark.usefixtures("mock_hub_run")
async def test_cover_id_migration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migrating unique id."""
    mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        COVER_DOMAIN, DOMAIN, 1234567890123, config_entry=mock_config_entry
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.async_block_till_done()
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entities) == 1
    assert entities[0].unique_id == "1234567890123"


@pytest.mark.usefixtures("mock_hub_run")
async def test_roller_update_writes_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a roller update from the hub writes the cover state."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    api = mock_config_entry.runtime_data.api
    with patch.object(aiopulse.Roller, "health_updater", AsyncMock()):
        roller = aiopulse.Roller(api, 1234567890123)
    roller.name = "Kitchen"
    roller.type = 1
    roller.closed_percent = 100
    api.rollers[roller.id] = roller
    api.notify_callback(aiopulse.UpdateType.rollers)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        COVER_DOMAIN, DOMAIN, "1234567890123"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).attributes[ATTR_CURRENT_POSITION] == 0

    roller.closed_percent = 40
    roller.notify_callback()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).attributes[ATTR_CURRENT_POSITION] == 60
