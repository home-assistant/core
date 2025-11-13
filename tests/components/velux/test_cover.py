"""Tests for the Velux cover platform."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.velux import DOMAIN
from homeassistant.const import STATE_CLOSED, STATE_OPEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import update_callback_entity

from tests.common import MockConfigEntry, SnapshotAssertion, snapshot_platform


@pytest.fixture
def platform() -> Platform:
    """Fixture to specify platform to test."""
    return Platform.COVER


@pytest.mark.usefixtures("setup_integration")
async def test_cover_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the cover entity (registry + state)."""
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )

    # Get the cover entity setup and test device association
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entity_entries) == 1
    entry = entity_entries[0]

    assert entry.device_id is not None
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry is not None
    assert (DOMAIN, f"{123456789}") in device_entry.identifiers
    assert device_entry.via_device_id is not None
    via_device_entry = device_registry.async_get(device_entry.via_device_id)
    assert via_device_entry is not None
    assert (
        DOMAIN,
        f"gateway_{mock_config_entry.entry_id}",
    ) in via_device_entry.identifiers


@pytest.mark.usefixtures("setup_integration")
async def test_cover_closed(
    hass: HomeAssistant,
    mock_window: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the cover closed state."""

    test_entity_id = "cover.test_window"

    # Initial state should be open
    state = hass.states.get(test_entity_id)
    assert state is not None
    assert state.state == STATE_OPEN

    # Update mock window position to closed percentage
    mock_window.position.position_percent = 100
    # Also directly set position to closed, so this test should
    # continue to be green after the lib is fixed
    mock_window.position.closed = True

    # Trigger entity state update via registered callback
    await update_callback_entity(hass, mock_window)

    state = hass.states.get(test_entity_id)
    assert state is not None
    assert state.state == STATE_CLOSED
