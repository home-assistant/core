"""Test the MTA sensor platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.freeze_time("2023-10-21")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_subway_sensor(
    hass: HomeAssistant,
    mock_config_entry_with_subway_subentry: MockConfigEntry,
    mock_subway_feed: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the subway sensor entities."""
    await hass.config.async_set_time_zone("UTC")

    mock_config_entry_with_subway_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(
        mock_config_entry_with_subway_subentry.entry_id
    )
    await hass.async_block_till_done()

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry_with_subway_subentry.entry_id
    )


@pytest.mark.freeze_time("2023-10-21")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_bus_sensor(
    hass: HomeAssistant,
    mock_config_entry_with_bus_subentry: MockConfigEntry,
    mock_bus_feed: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the bus sensor entities."""
    await hass.config.async_set_time_zone("UTC")

    mock_config_entry_with_bus_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_bus_subentry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry_with_bus_subentry.entry_id
    )
