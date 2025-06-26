"""Test the Stookwijzer init."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.stookwijzer.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_stookwijzer: MagicMock,
) -> None:
    """Test the Stookwijzer configuration entry loading and unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_stookwijzer.return_value.async_update.mock_calls) == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_stookwijzer: MagicMock,
) -> None:
    """Test the Stookwijzer configuration entry loading and unloading."""
    mock_stookwijzer.return_value.advice = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert len(mock_stookwijzer.return_value.async_update.mock_calls) == 1


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
        CONF_LATITUDE: 450000.123456789,
        CONF_LONGITUDE: 200000.123456789,
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
    mock_stookwijzer.async_transform_coordinates.return_value = None

    mock_v1_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_v1_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_v1_config_entry.state is ConfigEntryState.MIGRATION_ERROR
    assert issue_registry.async_get_issue(DOMAIN, "location_migration_failed")

    assert len(mock_stookwijzer.async_transform_coordinates.mock_calls) == 1


@pytest.mark.usefixtures("mock_stookwijzer")
async def test_entity_entry_migration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test successful migration of entry data."""
    mock_config_entry.add_to_hass(hass)
    entity = entity_registry.async_get_or_create(
        suggested_object_id="advice",
        disabled_by=None,
        domain=SENSOR_DOMAIN,
        platform=DOMAIN,
        unique_id=mock_config_entry.entry_id,
        config_entry=mock_config_entry,
    )

    assert entity.unique_id == mock_config_entry.entry_id

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(
            SENSOR_DOMAIN,
            DOMAIN,
            mock_config_entry.entry_id,
        )
        is None
    )

    assert (
        entity_registry.async_get_entity_id(
            SENSOR_DOMAIN,
            DOMAIN,
            f"{mock_config_entry.entry_id}_advice",
        )
        == "sensor.advice"
    )
