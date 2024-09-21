"""Tests for number platform."""

from unittest.mock import AsyncMock

from aioautomower.utils import mower_list_to_dictionary_dataclass

from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import TEST_MOWER_ID

from tests.common import MockConfigEntry, load_json_value_fixture


async def test_workarea_deleted(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test if work area is deleted after removed."""

    values = mower_list_to_dictionary_dataclass(
        load_json_value_fixture("mower.json", DOMAIN)
    )
    await setup_integration(hass, mock_config_entry)
    current_entries = len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    )

    del values[TEST_MOWER_ID].work_areas[123456]
    mock_automower_client.get_status.return_value = values
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    ) == (current_entries - 2)
