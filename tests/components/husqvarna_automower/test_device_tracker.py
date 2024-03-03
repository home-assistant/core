"""Tests for device tracker platform."""
from unittest.mock import AsyncMock, patch

from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device_tracker_states(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test lawn_mower state."""
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("device_tracker.test_mower_1")
    assert state is not None
    assert state.attributes["source_type"] == "gps"
    assert state.attributes["latitude"] == 35.5402913
    assert state.attributes["longitude"] == -82.5527055


async def test_device_tracker_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device tracker."""
    with patch(
        "homeassistant.components.husqvarna_automower.PLATFORMS",
        [Platform.DEVICE_TRACKER],
    ):
        await setup_integration(hass, mock_config_entry)
        entity_entries = er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )

        assert entity_entries
        for entity_entry in entity_entries:
            assert hass.states.get(entity_entry.entity_id) == snapshot(
                name=f"{entity_entry.entity_id}-state"
            )
            assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
