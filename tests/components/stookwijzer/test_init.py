"""Test the Stookwijzer init."""

from unittest.mock import MagicMock

from homeassistant.components.stookwijzer.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry


async def test_migrate_entry(
    hass: HomeAssistant,
    mock_v1_config_entry: MockConfigEntry,
    mock_stookwijzer: MagicMock,
) -> None:
    """Test successful migration of entry data."""
    assert mock_v1_config_entry.version == 1

    mock_v1_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_v1_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_v1_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_stookwijzer.async_transform_coordinates.mock_calls) == 1

    assert mock_v1_config_entry.version == 2
    assert mock_v1_config_entry.data == {
        CONF_LATITUDE: 200000.123456789,
        CONF_LONGITUDE: 450000.123456789,
    }


async def test_entry_migration_failure(
    hass: HomeAssistant,
    mock_v1_config_entry: MockConfigEntry,
    mock_stookwijzer: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test successful migration of entry data."""
    assert mock_v1_config_entry.version == 1

    # Failed getting the transformed coordinates
    mock_stookwijzer.async_transform_coordinates.return_value = (None, None)

    mock_v1_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_v1_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_v1_config_entry.state is ConfigEntryState.MIGRATION_ERROR
    assert issue_registry.async_get_issue(DOMAIN, "location_migration_failed")

    assert len(mock_stookwijzer.async_transform_coordinates.mock_calls) == 1
