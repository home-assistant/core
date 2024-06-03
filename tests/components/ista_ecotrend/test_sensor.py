"""Tests for the ista EcoTrend Sensors."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setup(
    hass: HomeAssistant,
    ista_config_entry: MockConfigEntry,
    mock_ista: MagicMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup of ista EcoTrend sensor platform."""

    ista_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(ista_config_entry.entry_id)
    await hass.async_block_till_done()

    assert ista_config_entry.state is ConfigEntryState.LOADED

    for entity in er.async_entries_for_config_entry(
        entity_registry, ista_config_entry.entry_id
    ):
        assert entity == snapshot
        assert hass.states.get(entity.entity_id) == snapshot

    for device in dr.async_entries_for_config_entry(
        device_registry, ista_config_entry.entry_id
    ):
        assert device == snapshot
